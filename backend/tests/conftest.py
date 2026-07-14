"""Shared test fixtures. Uses fakeredis so no live services are required."""
from __future__ import annotations

import os

import fakeredis.aioredis
import pytest

# Required env must exist before Settings is constructed. Set deterministic
# test values (these win over any local .env because env vars take precedence).
os.environ.setdefault("LIVEKIT_API_KEY", "testkey")
os.environ.setdefault("LIVEKIT_API_SECRET", "testsecret_at_least_32_chars_padding_xx")
os.environ.setdefault("NEXT_PUBLIC_LIVEKIT_URL", "ws://localhost:7880")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from backend.config import Settings  # noqa: E402
from backend.curriculum import load_exercise  # noqa: E402
from backend.store import Store  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(redis_client) -> Store:
    return Store(redis_client, default_cefr="A2", native_lang="en", target_lang="es")


@pytest.fixture
def exercise(settings):
    return load_exercise(settings.curriculum_dir)
