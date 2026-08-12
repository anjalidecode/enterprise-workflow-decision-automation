"""Load recruitment seed data from JSON. Files are never written by the runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_jobs() -> list[dict[str, Any]]:
    path = DATA_DIR / "jobs" / "jobs.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_candidates() -> list[dict[str, Any]]:
    path = DATA_DIR / "candidates" / "candidates.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_recruitment_policy() -> dict[str, Any]:
    path = DATA_DIR / "policies" / "recruitment_policy.json"
    return json.loads(path.read_text(encoding="utf-8"))
