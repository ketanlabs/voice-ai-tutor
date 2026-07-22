"""FastAPI app — session management + exercise content + learner state.

Exposes a small REST surface consumed by the voice agent and the frontend.
Built as a factory (`create_app`) so tests can inject a fakeredis client and an
in-memory exercise list. Run in production with:
    uvicorn backend.app:create_app --factory --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from . import tokens
from .config import Settings, get_settings
from .curriculum import load_exercise
from .models import (
    LANGUAGES,
    AttemptResult,
    ExerciseItem,
    LearnerProgress,
    LearnerSnapshot,
    ProgressScore,
    ReviewItems,
    SessionSummary,
    TokenRequest,
    TokenResponse,
    VocabCreate,
    VocabItem,
    WordProgress,
)
from .store import Store


def _build_store(settings: Settings, redis_client: Redis | None) -> Store:
    client = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
    return Store(
        client,
        default_cefr=settings.default_cefr_level,
        native_lang=settings.native_lang,
        target_lang=settings.target_lang,
    )


def create_app(
    *,
    settings: Settings | None = None,
    redis_client: Redis | None = None,
    exercise: list[ExerciseItem] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    exercise = exercise if exercise is not None else load_exercise(settings.curriculum_dir)
    store = _build_store(settings, redis_client)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        try:
            await store.redis.aclose()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    app = FastAPI(title="Lingua — Backend", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev; tighten to the frontend origin in production
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.store = store
    app.state.exercise = exercise

    # ---- dependencies -------------------------------------------------------
    def get_store(request: Request) -> Store:
        return request.app.state.store

    def get_cfg(request: Request) -> Settings:
        return request.app.state.settings

    # ---- health -------------------------------------------------------------
    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # ---- session / token ----------------------------------------------------
    @app.post("/session/token", response_model=TokenResponse)
    async def issue_token(
        body: TokenRequest,
        store: Store = Depends(get_store),
        cfg: Settings = Depends(get_cfg),
    ) -> TokenResponse:
        handle = body.handle.strip()
        if not handle:
            raise HTTPException(status_code=422, detail="handle must not be empty")
        # Memory is namespaced per language; the LiveKit identity stays the bare
        # handle so the coach greets by name.
        learner_id = f"{handle}:{body.language}"
        await store.get_or_create_learner(learner_id, target_lang=body.language)
        token = tokens.create_access_token(
            identity=handle,
            room=tokens.room_for_learner(learner_id),
            api_key=cfg.livekit_api_key,
            api_secret=cfg.livekit_api_secret,
            ttl_seconds=cfg.token_ttl_seconds,
            metadata=json.dumps({"language": body.language, "learner_id": learner_id}),
        )
        return TokenResponse(
            token=token,
            livekit_url=cfg.livekit_url,
            identity=handle,
            language=body.language,
        )

    # ---- exercise content ---------------------------------------------------
    @app.get("/exercise", response_model=list[ExerciseItem])
    async def get_exercise(request: Request):
        return request.app.state.exercise

    # ---- learner snapshot ---------------------------------------------------
    @app.get("/learners/{identity}", response_model=LearnerSnapshot)
    async def get_snapshot(identity: str, store: Store = Depends(get_store)):
        return await store.get_or_create_learner(identity)

    # ---- learner progress (curriculum joined with practice) -----------------
    @app.get("/learners/{identity}/progress", response_model=LearnerProgress)
    async def get_progress(
        identity: str, request: Request, store: Store = Depends(get_store)
    ):
        """Report progress by joining the curriculum (canonical English prompts)
        with the learner's practiced vocab + profile. One row per curriculum item;
        never-practiced words show zeros. `passed` is mastery (correct >= 1)."""
        snapshot = await store.get_or_create_learner(identity)
        vocab = {v.word: v for v in await store.get_vocab(identity)}
        exercise: list[ExerciseItem] = request.app.state.exercise

        # Language comes from the per-language identity ({handle}:{lang}); fall
        # back to the profile if the identity isn't namespaced.
        lang = identity.rsplit(":", 1)[-1]
        if lang not in LANGUAGES:
            lang = snapshot.profile.target_lang

        items: list[WordProgress] = []
        passed = 0
        for ex in exercise:
            v = vocab.get(ex.prompt)
            is_passed = bool(v and v.correct >= 1)
            passed += 1 if is_passed else 0
            items.append(
                WordProgress(
                    prompt=ex.prompt,
                    word=(v.translation if v else ""),
                    seen=(v.seen if v else 0),
                    correct=(v.correct if v else 0),
                    passed=is_passed,
                )
            )
        return LearnerProgress(
            identity=identity,
            language=lang,  # type: ignore[arg-type]
            profile=snapshot.profile,
            items=items,
            score=ProgressScore(passed=passed, total=len(exercise)),
        )

    # ---- vocab / SRS (each practiced prompt is an SRS item) -----------------
    @app.post("/learners/{identity}/vocab", response_model=VocabItem)
    async def add_vocab(
        identity: str, body: VocabCreate, store: Store = Depends(get_store)
    ):
        return await store.add_vocab(identity, body)

    @app.get("/learners/{identity}/review-items", response_model=ReviewItems)
    async def review_items(
        identity: str, n: int = 5, store: Store = Depends(get_store)
    ):
        items = await store.get_review_items(identity, n)
        return ReviewItems(items=items)

    @app.post("/learners/{identity}/attempt")
    async def record_attempt(
        identity: str, body: AttemptResult, store: Store = Depends(get_store)
    ):
        await store.record_attempt(identity, body)
        return {"ok": True}

    # ---- sessions -----------------------------------------------------------
    @app.post("/learners/{identity}/sessions")
    async def save_session(
        identity: str, body: SessionSummary, store: Store = Depends(get_store)
    ):
        await store.save_session_summary(identity, body)
        return {"ok": True}

    return app
