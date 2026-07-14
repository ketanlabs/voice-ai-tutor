"""LiveKit access-token issuance.

The backend is the single place LiveKit credentials are used — neither the
frontend nor the voice agent ever sees the API secret. The participant identity
is set to the learner's handle so all state keys line up across sessions.
"""
from __future__ import annotations

from datetime import timedelta

from livekit import api


def create_access_token(
    *,
    identity: str,
    room: str,
    api_key: str,
    api_secret: str,
    ttl_seconds: int = 3600,
    metadata: str | None = None,
) -> str:
    """Mint a JWT granting the learner join access to their room.

    `metadata` (a JSON string) is attached to the participant so the voice agent
    can read the chosen language on connect.
    """
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(grants)
        .with_ttl(timedelta(seconds=ttl_seconds))
    )
    if metadata is not None:
        token = token.with_metadata(metadata)
    return token.to_jwt()


def room_for_learner(identity: str) -> str:
    """Deterministic room name per learner (one live session at a time)."""
    return f"tutor-{identity}"
