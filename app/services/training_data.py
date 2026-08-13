"""Load fictional training seed JSON (read-only source files)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_training_courses() -> list[dict[str, Any]]:
    return list(_load_json(DATA_DIR / "training" / "courses.json"))


@lru_cache(maxsize=1)
def load_training_history() -> list[dict[str, Any]]:
    return list(_load_json(DATA_DIR / "training" / "history.json"))


@lru_cache(maxsize=1)
def load_training_skills() -> list[dict[str, Any]]:
    return list(_load_json(DATA_DIR / "training" / "skills.json"))


@lru_cache(maxsize=1)
def load_training_policy() -> dict[str, Any]:
    return dict(_load_json(DATA_DIR / "policies" / "training_policy.json"))
