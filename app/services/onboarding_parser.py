"""Parse onboarding requests into employee identifiers (deterministic, no LLM)."""

from __future__ import annotations

import re
from typing import Any

_EMPLOYEE_ID_RE = re.compile(r"\b(E\d{3})\b", re.IGNORECASE)


def parse_onboarding_request(user_request: str) -> dict[str, Any]:
    """Extract employee_id hints from an onboarding business request."""

    text = user_request.strip()
    lowered = text.lower()
    employee_id = None
    match = _EMPLOYEE_ID_RE.search(text)
    if match:
        employee_id = match.group(1).upper()

    return {
        "employee_id": employee_id,
        "query": text,
        "wants_onboarding": any(
            token in lowered
            for token in (
                "onboard",
                "onboarding",
                "new hire",
                "new employee",
                "joining",
                "start onboarding",
            )
        ),
    }
