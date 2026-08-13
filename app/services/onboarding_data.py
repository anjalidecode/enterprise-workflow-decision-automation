"""Load onboarding seed data from JSON. Files are never written by the runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_onboarding_documents() -> list[dict[str, Any]]:
    path = DATA_DIR / "onboarding" / "documents.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_onboarding_profiles() -> list[dict[str, Any]]:
    path = DATA_DIR / "onboarding" / "profiles.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_onboarding_policy() -> dict[str, Any]:
    path = DATA_DIR / "policies" / "onboarding_policy.json"
    return json.loads(path.read_text(encoding="utf-8"))
