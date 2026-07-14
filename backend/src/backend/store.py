"""Redis-backed persistence — the ONLY place in the system that touches Redis.

Owns the learner profile, practiced-prompt SRS state, per-skill stats, and session
summaries. Everything is keyed by the learner's per-language identity
(`{handle}:{lang}`), which is what makes cross-session memory work.
"""
from __future__ import annotations

import json
import time

from redis.asyncio import Redis

from . import srs
from .models import (
    AttemptResult,
    LearnerSnapshot,
    Profile,
    SessionSummary,
    VocabCreate,
    VocabItem,
)


def _k(identity: str, suffix: str) -> str:
    return f"learner:{identity}:{suffix}"


class Store:
    """Async wrapper over Redis. Inject the client so tests can use fakeredis."""

    def __init__(self, redis: Redis, *, default_cefr: str = "A2",
                 native_lang: str = "en", target_lang: str = "es") -> None:
        self.redis = redis
        self.default_cefr = default_cefr
        self.native_lang = native_lang
        self.target_lang = target_lang

    # --- profile -------------------------------------------------------------
    async def get_profile(self, identity: str) -> Profile | None:
        raw = await self.redis.get(_k(identity, "profile"))
        return Profile.model_validate_json(raw) if raw else None

    async def _save_profile(self, identity: str, profile: Profile) -> None:
        await self.redis.set(_k(identity, "profile"), profile.model_dump_json())

    # --- learner lifecycle ---------------------------------------------------
    async def get_or_create_learner(
        self, identity: str, target_lang: str | None = None
    ) -> LearnerSnapshot:
        """Load a learner, creating a fresh profile on first contact.

        `target_lang` sets the language on creation (learners are namespaced per
        language upstream, so this just records it on the profile).
        """
        now = time.time()
        profile = await self.get_profile(identity)
        if profile is None:
            profile = Profile(
                cefr_level=self.default_cefr,  # type: ignore[arg-type]
                native_lang=self.native_lang,
                target_lang=target_lang or self.target_lang,
                created_at=now,
                last_seen=now,
            )
        else:
            profile.last_seen = now
        await self._save_profile(identity, profile)
        return LearnerSnapshot(identity=identity, profile=profile)

    # --- vocab ---------------------------------------------------------------
    async def get_vocab(self, identity: str) -> list[VocabItem]:
        raw = await self.redis.hgetall(_k(identity, "vocab"))
        return [VocabItem.model_validate_json(v) for v in raw.values()]

    async def add_vocab(self, identity: str, item: VocabCreate) -> VocabItem:
        """Insert or update a vocab word. New words are immediately due."""
        key = _k(identity, "vocab")
        existing = await self.redis.hget(key, item.word)
        if existing:
            vocab = VocabItem.model_validate_json(existing)
            vocab.translation = item.translation or vocab.translation
            vocab.example = item.example or vocab.example
        else:
            vocab = VocabItem(
                word=item.word,
                translation=item.translation,
                example=item.example,
                due_at=time.time(),  # brand-new word is due now
            )
        await self.redis.hset(key, item.word, vocab.model_dump_json())
        return vocab

    async def get_review_items(self, identity: str, n: int) -> list[VocabItem]:
        vocab = await self.get_vocab(identity)
        return srs.select_review_items(vocab, n, now=time.time())

    # --- pronunciation attempts (SRS + per-skill stats) ----------------------
    async def record_attempt(self, identity: str, result: AttemptResult) -> None:
        now = time.time()
        # 1) Update SRS state for the practiced prompt/word.
        if result.word:
            key = _k(identity, "vocab")
            existing = await self.redis.hget(key, result.word)
            vocab = (
                VocabItem.model_validate_json(existing)
                if existing
                else VocabItem(word=result.word, translation=result.translation, due_at=now)
            )
            if result.translation:
                vocab.translation = result.translation
            srs.schedule_after_review(vocab, result.correct, now)
            await self.redis.hset(key, result.word, vocab.model_dump_json())

        # 2) Aggregate per-skill stats (e.g. pronunciation accuracy over time).
        skill_key = _k(identity, "skills")
        raw = await self.redis.hget(skill_key, result.skill)
        stats = json.loads(raw) if raw else {"seen": 0, "correct": 0}
        stats["seen"] += 1
        stats["correct"] += 1 if result.correct else 0
        await self.redis.hset(skill_key, result.skill, json.dumps(stats))

    async def get_skill_stats(self, identity: str) -> dict[str, dict]:
        raw = await self.redis.hgetall(_k(identity, "skills"))
        return {skill: json.loads(v) for skill, v in raw.items()}

    # --- sessions ------------------------------------------------------------
    async def save_session_summary(self, identity: str, summary: SessionSummary) -> None:
        await self.redis.rpush(_k(identity, "sessions"), summary.model_dump_json())

    async def get_sessions(self, identity: str) -> list[SessionSummary]:
        raw = await self.redis.lrange(_k(identity, "sessions"), 0, -1)
        return [SessionSummary.model_validate_json(s) for s in raw]
