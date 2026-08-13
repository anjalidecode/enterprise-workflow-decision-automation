"""Parse training requests into employee and operation scope."""

from __future__ import annotations

import re
from typing import Any

_EMPLOYEE_ID_RE = re.compile(r"\b(E\d{3})\b", re.IGNORECASE)


def parse_training_request(user_request: str) -> dict[str, Any]:
    """Extract training request scope from a business request."""

    text = user_request.strip()
    lowered = text.lower()
    employee_id = None
    match = _EMPLOYEE_ID_RE.search(text)
    if match:
        employee_id = match.group(1).upper()

    if any(
        token in lowered
        for token in ("skill gap", "skill gaps", "identify skill", "skills gap")
    ):
        operation = "skill_gap"
    elif any(
        token in lowered
        for token in ("training plan", "create a training plan", "development plan")
    ):
        operation = "training_plan"
    elif any(token in lowered for token in ("enroll", "enrollment", "assign training")):
        operation = "enroll"
    elif any(
        token in lowered
        for token in ("recommend", "suitable training", "find suitable", "course")
    ):
        operation = "recommend"
    else:
        operation = "recommend"

    return {
        "employee_id": employee_id,
        "operation": operation,
        "query": text,
        "wants_training": any(
            token in lowered
            for token in (
                "training",
                "course",
                "courses",
                "skill gap",
                "skill development",
                "upskilling",
                "reskilling",
                "learning",
                "training plan",
            )
        ),
    }
