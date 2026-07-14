"""Voice-agent configuration — read exclusively from environment (.env at repo root)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LiveKit connection (the agents CLI also reads these automatically).
    livekit_url: str = Field("ws://livekit:7880", alias="LIVEKIT_URL")
    livekit_api_key: str = Field("devkey", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field("secret", alias="LIVEKIT_API_SECRET")

    # Backend API (session/state service) — the agent's only state dependency.
    backend_url: str = Field("http://backend:8000", alias="BACKEND_URL")

    # Provider selection.
    use_livekit_inference: bool = Field(False, alias="USE_LIVEKIT_INFERENCE")
    stt_provider: str = Field("deepgram", alias="STT_PROVIDER")
    llm_provider: str = Field("anthropic", alias="LLM_PROVIDER")
    tts_provider: str = Field("cartesia", alias="TTS_PROVIDER")

    # Provider keys (only those matching the selected providers are needed).
    deepgram_api_key: str = Field("", alias="DEEPGRAM_API_KEY")
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    cartesia_api_key: str = Field("", alias="CARTESIA_API_KEY")
    elevenlabs_api_key: str = Field("", alias="ELEVENLABS_API_KEY")
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")

    # Model / voice tuning.
    llm_model: str = Field("claude-sonnet-5", alias="LLM_MODEL")
    stt_model: str = Field("nova-3", alias="STT_MODEL")
    tts_model: str = Field("sonic-3", alias="TTS_MODEL")
    tts_voice_id: str = Field("", alias="TTS_VOICE_ID")

    # Tutor language config.
    target_lang: str = Field("es", alias="TARGET_LANG")
    native_lang: str = Field("en", alias="NATIVE_LANG")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
