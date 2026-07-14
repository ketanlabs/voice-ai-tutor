"""Shared domain models (pydantic) — the vocabulary of the backend API.

These shapes are the contract the voice + frontend clients rely on.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

# Languages the coach can teach. Extend this to add more (content is one English
# file, translated at runtime, so no per-language authoring is required).
Language = Literal["es", "fr", "it"]
LANGUAGES: tuple[str, ...] = ("es", "fr", "it")


# ------------------------------------------------------------- exercise -------
class ExerciseItem(BaseModel):
    """One picture-pronunciation item (authored once in English)."""

    prompt: str                 # English word OR short sentence (translated at runtime)
    image: str = ""             # frontend path, e.g. /flashcards/apple.jpg
    emoji: str = ""             # fallback shown if the image is missing


# ------------------------------------------------------------ learner state ---
class Profile(BaseModel):
    cefr_level: CEFRLevel = "A2"
    native_lang: str = "en"
    target_lang: str = "es"
    created_at: float = 0.0
    last_seen: float = 0.0


class VocabItem(BaseModel):
    """SRS record — here, one practiced prompt (word/sentence)."""

    word: str
    translation: str
    example: str = ""
    seen: int = 0
    correct: int = 0
    ease: float = 2.5          # SM-2-style ease factor
    due_at: float = 0.0        # unix ts when this item is next due for review


class SessionSummary(BaseModel):
    started_at: float = 0.0
    ended_at: float = 0.0
    topics: list[str] = Field(default_factory=list)
    new_words: list[str] = Field(default_factory=list)
    score: float | None = None
    notes: str = ""


class LearnerSnapshot(BaseModel):
    """What the voice agent needs to resume a learner (per language)."""

    identity: str
    profile: Profile


# ------------------------------------------------------- request/response -----
class TokenRequest(BaseModel):
    handle: str = Field(..., min_length=1, max_length=64)
    language: Language = "es"


class TokenResponse(BaseModel):
    token: str
    livekit_url: str
    identity: str
    language: Language


class VocabCreate(BaseModel):
    word: str
    translation: str
    example: str = ""


class AttemptResult(BaseModel):
    """The outcome of one pronunciation attempt."""

    word: str | None = None        # the English prompt (stable identifier)
    translation: str = ""          # its translation in the target language
    correct: bool
    skill: str = "pronunciation"


class ReviewItems(BaseModel):
    items: list[VocabItem]
