"""Tests for exercise loading + schema validation (fails loudly on bad YAML)."""
from __future__ import annotations

import pytest

from backend.curriculum import CurriculumError, load_exercise

GOOD = """
items:
  - prompt: "apple"
    image: /flashcards/apple.jpg
    emoji: "🍎"
  - prompt: "I eat an apple."
"""


def test_real_exercise_loads(exercise):
    assert len(exercise) >= 1
    first = exercise[0]
    assert first.prompt and first.image  # shipped items have images


def test_good_fixture_loads(tmp_path):
    (tmp_path / "exercise.yaml").write_text(GOOD)
    items = load_exercise(tmp_path)
    assert items[0].prompt == "apple"
    assert items[0].image == "/flashcards/apple.jpg"
    assert items[1].prompt == "I eat an apple."  # image/emoji optional


def test_missing_file_raises(tmp_path):
    with pytest.raises(CurriculumError, match="not found"):
        load_exercise(tmp_path)


def test_missing_prompt_raises(tmp_path):
    (tmp_path / "exercise.yaml").write_text('items:\n  - image: "/x.jpg"\n')
    with pytest.raises(CurriculumError, match="schema validation"):
        load_exercise(tmp_path)


def test_empty_list_raises(tmp_path):
    (tmp_path / "exercise.yaml").write_text("items: []\n")
    with pytest.raises(CurriculumError, match="non-empty list"):
        load_exercise(tmp_path)
