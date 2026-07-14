"""Tests for the Redis store via fakeredis — persistence + memory correctness."""
from __future__ import annotations

import pytest

from backend.models import AttemptResult, SessionSummary, VocabCreate

pytestmark = pytest.mark.asyncio


async def test_get_or_create_learner_is_idempotent(store):
    snap = await store.get_or_create_learner("alice:es", target_lang="es")
    assert snap.identity == "alice:es"
    assert snap.profile.target_lang == "es"
    first_seen = snap.profile.last_seen

    again = await store.get_or_create_learner("alice:es")
    assert again.profile.created_at == snap.profile.created_at  # not recreated
    assert again.profile.last_seen >= first_seen


async def test_pronunciation_attempt_updates_srs_and_stats(store):
    await store.get_or_create_learner("cara:fr", target_lang="fr")
    # Keyed by the English prompt; translation stored for display.
    await store.record_attempt(
        "cara:fr",
        AttemptResult(word="apple", translation="pomme", correct=True, skill="pronunciation"),
    )
    vocab = {v.word: v for v in await store.get_vocab("cara:fr")}
    assert vocab["apple"].seen == 1 and vocab["apple"].correct == 1
    assert vocab["apple"].translation == "pomme"

    stats = await store.get_skill_stats("cara:fr")
    assert stats["pronunciation"] == {"seen": 1, "correct": 1}


async def test_weak_words_surface_first_in_review(store):
    await store.get_or_create_learner("val:es", target_lang="es")
    # "casa" missed, "gato" nailed → casa should rank ahead of gato.
    await store.record_attempt("val:es", AttemptResult(word="house", translation="casa", correct=False))
    await store.record_attempt("val:es", AttemptResult(word="cat", translation="gato", correct=True))
    ranked = [v.word for v in await store.get_review_items("val:es", 5)]
    assert ranked and ranked[0] == "house"  # the weak one is most urgent


async def test_review_items_returns_due_words(store):
    await store.get_or_create_learner("finn:it", target_lang="it")
    await store.add_vocab("finn:it", VocabCreate(word="mela", translation="apple"))
    items = await store.get_review_items("finn:it", 5)
    assert [i.word for i in items] == ["mela"]  # new word is immediately due


async def test_session_summary_persist(store):
    await store.get_or_create_learner("eve:es")
    await store.save_session_summary("eve:es", SessionSummary(new_words=["manzana"]))
    sessions = await store.get_sessions("eve:es")
    assert len(sessions) == 1 and sessions[0].new_words == ["manzana"]
