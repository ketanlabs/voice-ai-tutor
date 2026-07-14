"""Spaced-repetition scheduling + selection — so weak words resurface first.

A deliberately small SM-2-flavoured scheme over the VocabItem fields we persist
(seen / correct / ease / due_at). Pure functions so they are trivially unit
testable without Redis. `now` is always injected for determinism.
"""
from __future__ import annotations

from .models import VocabItem

# Base review interval. Kept in hours (not days) so a tutoring demo actually
# resurfaces items across nearby sessions instead of weeks later.
BASE_INTERVAL_SECONDS = 6 * 3600
MIN_EASE = 1.3
MAX_EASE = 3.0
RETRY_SECONDS = 60  # an item answered wrong is due again almost immediately


def schedule_after_review(item: VocabItem, correct: bool, now: float) -> VocabItem:
    """Update an item's ease + next due time after a review attempt.

    Correct answers raise ease and push the item further out; incorrect answers
    lower ease and make the item due again right away.
    """
    item.seen += 1
    if correct:
        item.correct += 1
        item.ease = min(MAX_EASE, round(item.ease + 0.1, 4))
        interval = BASE_INTERVAL_SECONDS * item.ease * max(1, item.correct)
        item.due_at = now + interval
    else:
        item.ease = max(MIN_EASE, round(item.ease - 0.2, 4))
        item.due_at = now + RETRY_SECONDS
    return item


def _urgency_key(item: VocabItem, now: float) -> tuple:
    """Sort key: most-in-need-of-practice first."""
    overdue = 0 if item.due_at <= now else 1
    accuracy = (item.correct / item.seen) if item.seen else 0.0
    return (overdue, accuracy, item.ease, item.due_at)


def select_review_items(items: list[VocabItem], n: int, now: float) -> list[VocabItem]:
    """Pick the `n` items most worth practicing right now.

    Overdue items come first, then the weakest (lowest accuracy / ease). A brand
    new learner with no vocab yields an empty list (caller falls back to the
    curriculum).
    """
    if n <= 0 or not items:
        return []
    return sorted(items, key=lambda it: _urgency_key(it, now))[:n]
