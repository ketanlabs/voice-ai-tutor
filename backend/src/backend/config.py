"""Backend configuration — read exclusively from environment (.env at repo root).

No secrets are hardcoded. Required values fail fast at startup so a
misconfigured deployment surfaces immediately rather than at first request.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is two parents up from this file's package dir:
# backend/src/backend/config.py -> repo root is .../voice-ai-tutor
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All backend settings. Field names map to upper-cased env vars."""

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LiveKit credentials — the backend is the ONLY component that mints tokens.
    livekit_api_key: str = Field(..., alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(..., alias="LIVEKIT_API_SECRET")
    # URL handed to the browser inside the token response.
    livekit_url: str = Field(..., alias="NEXT_PUBLIC_LIVEKIT_URL")

    # State store — Redis is owned solely by the backend.
    redis_url: str = Field("redis://redis:6379/0", alias="REDIS_URL")

    # Where the curriculum YAML lives (relative to the backend package root).
    curriculum_dir: Path = Field(
        default=Path(__file__).resolve().parents[2] / "curriculum",
        alias="CURRICULUM_DIR",
    )

    # Tutor defaults.
    target_lang: str = Field("es", alias="TARGET_LANG")
    native_lang: str = Field("en", alias="NATIVE_LANG")
    default_cefr_level: str = Field("A2", alias="DEFAULT_CEFR_LEVEL")

    # Token time-to-live in seconds (session length ceiling).
    token_ttl_seconds: int = Field(3600, alias="TOKEN_TTL_SECONDS")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()  # type: ignore[call-arg]
