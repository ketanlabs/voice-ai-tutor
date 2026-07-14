"""Entrypoint / glue for the voice agent.

Wires the two layers together per job: on connect it reads the chosen language,
loads the exercise list, builds the AI pipeline, constructs the LinguaTutor
pronunciation-coach agent, and starts the session — greeting the learner and
launching the exercise. On shutdown it persists a session summary.

Run (from the voice/ dir, with src on the path — see Dockerfile):
    python -m voice.agent dev              # local dev
    python -m voice.agent start            # production
    python -m livekit.agents download-files  # prefetch VAD + turn-detector models
"""
from __future__ import annotations

import asyncio
import json
import logging

from livekit.agents import JobContext, JobProcess, WorkerOptions, cli

from . import pipeline, prompts, ui_events
from .backend_client import BackendClient
from .config import get_settings
from .tutor import LinguaTutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice.agent")


def prewarm(proc: JobProcess) -> None:
    """Load the (slow) VAD model once per worker process, before any call."""
    proc.userdata["vad"] = pipeline.load_vad()


def _lead_with_weak_words(
    items: list[dict], review: list[dict]
) -> tuple[list[dict], int]:
    """Reorder the exercise so previously-weak/overdue words come first.

    `review` is the SRS-ranked list (most in need first), keyed by the English
    prompt. Weak words that mispronounced before lead; the rest keep authored
    order. Brand-new learners (empty review) get the list unchanged.
    """
    by_prompt = {it["prompt"]: it for it in items}
    weak_prompts: list[str] = []
    for r in review:
        w = r.get("word")
        # Only lead with words actually gotten wrong at least once.
        if w in by_prompt and r.get("seen", 0) > r.get("correct", 0) and w not in weak_prompts:
            weak_prompts.append(w)
    lead = [by_prompt[w] for w in weak_prompts]
    rest = [it for it in items if it["prompt"] not in set(weak_prompts)]
    return lead + rest, len(lead)


def _friendly_error(err: object) -> str:
    """Turn a provider/pipeline error into a short, user-facing message."""
    text = str(getattr(err, "error", None) or err).lower()
    if any(k in text for k in ("429", "quota", "insufficient_quota", "rate limit")):
        return (
            "The speech service is unavailable (quota/rate limit exceeded). "
            "Check the provider's billing or limits, then reconnect."
        )
    if any(k in text for k in ("401", "unauthorized", "api key", "invalid_api_key")):
        return "The speech service rejected the API key. Check your provider credentials."
    return "The tutor hit a problem and had to stop. Please try reconnecting."


async def entrypoint(ctx: JobContext) -> None:
    cfg = get_settings()
    await ctx.connect()

    # The participant identity IS the learner's handle (set by the backend token),
    # which is what makes cross-session memory line up.
    participant = await ctx.wait_for_participant()
    identity = participant.identity

    # Language + per-language learner_id ride in participant metadata (set by the
    # backend token). identity (the bare handle) is the display name for greeting.
    language, learner_id = "es", f"{identity}:es"
    try:
        if participant.metadata:
            meta = json.loads(participant.metadata)
            language = meta.get("language", "es")
            learner_id = meta.get("learner_id", f"{identity}:{language}")
    except (ValueError, TypeError):
        pass
    logger.info("learner connected: %s lang=%s (room=%s)", identity, language, ctx.room.name)

    backend = BackendClient(cfg.backend_url)
    try:
        items = await backend.get_exercise()
        # Returning learners: lead with the words they previously struggled with
        # (spaced-repetition), then the rest of the list in its authored order.
        review = await backend.get_review_items(learner_id, n=len(items))
    except Exception:
        logger.exception("failed to load the exercise from backend")
        await backend.aclose()
        raise

    items, resumed = _lead_with_weak_words(items, review)
    logger.info("exercise ordered: %d weak-first / %d total", resumed, len(items))

    instructions = prompts.build_instructions(
        name=identity, language=language, items=items, resuming=resumed > 0
    )

    session = pipeline.build_session(cfg, ctx.proc.userdata["vad"], language)
    agent = LinguaTutor(
        instructions=instructions,
        backend=backend,
        identity=learner_id,
        room=ctx.room,
        items=items,
    )

    async def on_shutdown() -> None:
        # Persist what happened this session so the learner is "remembered".
        try:
            await backend.save_session(
                learner_id, topics=["pronunciation"], new_words=agent.new_words
            )
        except Exception:
            logger.exception("failed to save session summary")
        finally:
            await backend.aclose()

    ctx.add_shutdown_callback(on_shutdown)

    # Surface fatal pipeline errors (e.g. STT/TTS provider 429/quota) in the UI so
    # the learner sees a clear message instead of silent dead air.
    def _emit_error(err: object, fatal: bool) -> None:
        message = _friendly_error(err)
        logger.error("pipeline error (fatal=%s): %s", fatal, err)
        try:
            asyncio.create_task(
                ui_events.emit_ui(ctx.room, "error", {"message": message, "fatal": fatal})
            )
        except RuntimeError:  # loop already closing
            pass

    @session.on("error")
    def _on_error(ev) -> None:  # ErrorEvent: .error/.source
        err = getattr(ev, "error", ev)
        _emit_error(err, fatal=not getattr(err, "recoverable", False))

    @session.on("close")
    def _on_close(ev) -> None:  # CloseEvent: .error/.reason
        err = getattr(ev, "error", None)
        if err is not None:
            _emit_error(err, fatal=True)

    await session.start(agent, room=ctx.room)
    # Kick off: greet by name, explain the exercise, and show the first picture.
    await session.generate_reply(
        instructions=(
            f"Greet {identity} by name IN ENGLISH, briefly explain the pronunciation "
            f"exercise in English, then immediately show the first item (say only the "
            f"target word/sentence in the language being practiced)."
        )
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
