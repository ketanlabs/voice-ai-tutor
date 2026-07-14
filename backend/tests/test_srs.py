"""Unit tests for spaced-repetition scheduling + selection."""
from __future__ import annotations

from backend import srs
from backend.models import VocabItem

NOW = 1_000_000.0


def test_correct_answer_raises_ease_and_pushes_due_out():
    item = VocabItem(word="gato", translation="cat", ease=2.5, due_at=NOW)
    srs.schedule_after_review(item, correct=True, now=NOW)
    assert item.seen == 1
    assert item.correct == 1
    assert item.ease == 2.6
    # Next review is comfortably in the future.
    assert item.due_at > NOW + srs.BASE_INTERVAL_SECONDS


def test_wrong_answer_lowers_ease_and_makes_item_due_soon():
    item = VocabItem(word="perro", translation="dog", ease=2.5, due_at=NOW + 99999)
    srs.schedule_after_review(item, correct=False, now=NOW)
    assert item.seen == 1
    assert item.correct == 0
    assert item.ease == 2.3
    assert item.due_at == NOW + srs.RETRY_SECONDS


def test_ease_is_clamped():
    low = VocabItem(word="a", translation="a", ease=srs.MIN_EASE)
    srs.schedule_after_review(low, correct=False, now=NOW)
    assert low.ease == srs.MIN_EASE

    high = VocabItem(word="b", translation="b", ease=srs.MAX_EASE, correct=5)
    srs.schedule_after_review(high, correct=True, now=NOW)
    assert high.ease == srs.MAX_EASE


def test_selection_prioritises_overdue_then_weakest():
    overdue_weak = VocabItem(word="w", translation="", seen=4, correct=1, due_at=NOW - 10)
    overdue_strong = VocabItem(word="s", translation="", seen=4, correct=4, due_at=NOW - 10)
    not_due = VocabItem(word="n", translation="", seen=4, correct=1, due_at=NOW + 10_000)

    picked = srs.select_review_items([not_due, overdue_strong, overdue_weak], n=2, now=NOW)
    assert [i.word for i in picked] == ["w", "s"]  # both overdue, weakest first


def test_selection_edge_cases():
    assert srs.select_review_items([], n=5, now=NOW) == []
    item = VocabItem(word="x", translation="", due_at=NOW)
    assert srs.select_review_items([item], n=0, now=NOW) == []
