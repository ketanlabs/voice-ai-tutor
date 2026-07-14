"""(b) The conversation layer: the pronunciation-coach agent and its tools.

Tools are thin wrappers that push UI events to the frontend (image + 👍/👎) and
record results via the backend API. No Redis, no content files, no LiveKit secrets
here — all of that lives behind the backend.
"""
from __future__ import annotations

import logging

from livekit import rtc
from livekit.agents import Agent, RunContext, function_tool

from . import ui_events
from .backend_client import BackendClient

logger = logging.getLogger("voice.tutor")


class LinguaTutor(Agent):
    def __init__(
        self,
        *,
        instructions: str,
        backend: BackendClient,
        identity: str,
        room: rtc.Room,
        items: list[dict],
    ) -> None:
        super().__init__(instructions=instructions)
        self._backend = backend
        self._identity = identity  # per-language learner_id
        self._room = room
        self._items = {i["prompt"]: i for i in items}
        self._total = len(items)
        self._index = 0            # items shown so far (for progress display)
        self.correct = 0
        self.attempts = 0
        self.new_words: list[str] = []

    async def _emit(self, event_type: str, payload: dict) -> None:
        await ui_events.emit_ui(self._room, event_type, payload)

    @function_tool
    async def show_item(self, ctx: RunContext, prompt_en: str, prompt_target: str) -> str:
        """Show the picture for `prompt_en` (the English word/sentence from the list)
        and prepare to practice `prompt_target` (your translation into the target
        language). Call once per item, THEN say the target aloud and ask the learner
        to repeat it."""
        item = self._items.get(prompt_en)
        self._index += 1
        await self._emit(
            "item",
            {
                "image": (item or {}).get("image", ""),
                "emoji": (item or {}).get("emoji", ""),
                "prompt_en": prompt_en,
                "prompt_target": prompt_target,
                "index": self._index,
                "total": self._total,
            },
        )
        return (
            f"Showing '{prompt_en}'. Say '{prompt_target}' clearly, then ask the "
            f"learner to repeat it."
        )

    @function_tool
    async def score_item(
        self, ctx: RunContext, prompt_en: str, prompt_target: str,
        passed: bool, tip: str = "",
    ) -> str:
        """Record the learner's attempt and show 👍 (passed=true) or 👎 (false).
        Base it on whether the transcript matched '{prompt_target}' (ignore accents/
        case). On 👎, model the word once more. Then move to the next item."""
        self.attempts += 1
        if passed:
            self.correct += 1
        if prompt_target not in self.new_words:
            self.new_words.append(prompt_target)
        await self._emit("item_result", {"passed": passed, "tip": tip})
        try:
            # Key SRS by the English prompt — the stable, cross-language identifier
            # for the exercise item — so weak words can lead the next session.
            await self._backend.record_attempt(
                self._identity, correct=passed, word=prompt_en,
                translation=prompt_target, skill="pronunciation",
            )
        except Exception:
            logger.exception("failed to record pronunciation attempt")
        remaining = self._total - self._index
        if remaining > 0:
            return f"Recorded. {remaining} item(s) left — show the next one."
        return "Recorded. That was the last item — call finish_exercise."

    @function_tool
    async def finish_exercise(self, ctx: RunContext) -> str:
        """End the exercise once all items are done. Shows the final score."""
        await self._emit("exercise_end", {"correct": self.correct, "total": self.attempts})
        return (
            f"Exercise complete: {self.correct}/{self.attempts}. Congratulate the "
            f"learner warmly and invite them to practice again."
        )
