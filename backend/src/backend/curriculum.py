"""Load + validate the exercise list (picture-pronunciation items) from YAML.

The list is read-only authored content in a single English file, identical for all
languages (the coach translates each prompt at runtime). Loaded + validated at
startup; malformed content fails loudly with a clear error.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import ExerciseItem


class CurriculumError(ValueError):
    """Raised when exercise YAML is missing, malformed, or inconsistent."""


def _load_list(path: Path, key: str) -> list[dict]:
    if not path.exists():
        raise CurriculumError(f"Exercise file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough
        raise CurriculumError(f"Invalid YAML in {path.name}: {exc}") from exc
    if not isinstance(data, dict) or key not in data:
        raise CurriculumError(f"{path.name} must be a mapping with a top-level '{key}:' list")
    items = data[key]
    if not isinstance(items, list) or not items:
        raise CurriculumError(f"'{key}' in {path.name} must be a non-empty list")
    return items


def load_exercise(base_dir: Path) -> list[ExerciseItem]:
    """Load + validate the ordered exercise list from base_dir/exercise.yaml.

    List order = play order. Raises CurriculumError on any problem.
    """
    raw = _load_list(base_dir / "exercise.yaml", "items")
    try:
        return [ExerciseItem(**item) for item in raw]
    except ValidationError as exc:
        raise CurriculumError(f"Exercise failed schema validation:\n{exc}") from exc
