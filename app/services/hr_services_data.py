"""Load fictional HR services seed JSON (read-only source files)."""

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
def load_hr_service_requests() -> list[dict[str, Any]]:
    return list(_load_json(DATA_DIR / "hr_services" / "requests.json"))


@lru_cache(maxsize=1)
def load_hr_services_policy() -> dict[str, Any]:
    return dict(_load_json(DATA_DIR / "policies" / "hr_services_policy.json"))
