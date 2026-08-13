"""Load attendance seed data from JSON. Files are never written by the runtime."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_attendance_records() -> list[dict[str, Any]]:
    path = DATA_DIR / "attendance" / "attendance_records.json"
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError("attendance_records.json must contain a list of records")
    return payload


@lru_cache(maxsize=1)
def load_attendance_policy() -> dict[str, Any]:
    path = DATA_DIR / "policies" / "attendance_policy.json"
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("attendance_policy.json must contain a policy object")
    return payload
