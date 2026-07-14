"""Push structured UI events to the frontend over the LiveKit data channel.

The frontend subscribes to the ``tutor-ui`` topic and renders these as the
flashcard image, progress, and the 👍/👎 result. This is a one-way side channel —
the spoken audio itself flows through the media tracks as usual.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from livekit import rtc

logger = logging.getLogger("voice.ui")

UI_TOPIC = "tutor-ui"


async def emit_ui(room: rtc.Room, event_type: str, payload: dict[str, Any]) -> None:
    """Send a `{type, data}` JSON event to the learner's browser."""
    message = json.dumps({"type": event_type, "data": payload})
    try:
        await room.local_participant.publish_data(
            message, reliable=True, topic=UI_TOPIC
        )
    except Exception:  # pragma: no cover - UI is best-effort, never break the call
        logger.exception("failed to emit UI event %s", event_type)
