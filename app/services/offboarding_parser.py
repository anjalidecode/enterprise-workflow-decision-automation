"""Parse offboarding requests into employee and operation scope."""

from __future__ import annotations

import re
from typing import Any

_EMPLOYEE_ID_RE = re.compile(r"\b(E\d{3})\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def parse_offboarding_request(user_request: str) -> dict[str, Any]:
    """Extract offboarding request scope from a business request."""

    text = user_request.strip()
    lowered = text.lower()
    employee_id = None
    match = _EMPLOYEE_ID_RE.search(text)
    if match:
        employee_id = match.group(1).upper()

    requested_date = None
    date_match = _DATE_RE.search(text)
    if date_match:
        requested_date = date_match.group(1)

    if any(token in lowered for token in ("exit checklist", "create an exit checklist", "checklist")):
        operation = "checklist"
    elif any(token in lowered for token in ("ready for offboarding", "check whether", "readiness")):
        operation = "readiness"
    elif any(token in lowered for token in ("resignation", "resign", "process resignation")):
        operation = "resignation"
    elif any(token in lowered for token in ("offboard", "offboarding", "employee exit", "exit process")):
        operation = "start_offboarding"
    else:
        operation = "start_offboarding"

    exit_type = "voluntary_resignation"
    if "involuntary" in lowered or "termination" in lowered:
        exit_type = "involuntary"
    elif "retirement" in lowered:
        exit_type = "retirement"

    return {
        "employee_id": employee_id,
        "operation": operation,
        "exit_type": exit_type,
        "requested_date": requested_date,
        "query": text,
        "wants_offboarding": any(
            token in lowered
            for token in (
                "offboard",
                "offboarding",
                "resign",
                "resignation",
                "exit checklist",
                "employee exit",
                "exit process",
                "last working day",
            )
        ),
    }
