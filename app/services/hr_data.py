"""Read-only access to simulated HR enterprise data."""

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
def load_employees() -> list[dict[str, Any]]:
    payload = _read_json(DATA_DIR / "employees" / "employees.json")
    if not isinstance(payload, list):
        raise ValueError("employees.json must contain a list of employees")
    return payload


@lru_cache(maxsize=1)
def load_leave_policy() -> dict[str, Any]:
    payload = _read_json(DATA_DIR / "policies" / "leave_policy.json")
    if not isinstance(payload, dict):
        raise ValueError("leave_policy.json must contain a policy object")
    return payload


def get_employee(employee_id: str) -> dict[str, Any] | None:
    """Return a copy of the employee record, or None if not found."""

    target = employee_id.strip().upper()
    for employee in load_employees():
        if str(employee.get("employee_id", "")).upper() == target:
            return dict(employee)
    return None
