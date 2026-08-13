"""Parse performance requests into employee, period, and operation scope."""

from __future__ import annotations

import re
from typing import Any

_EMPLOYEE_ID_RE = re.compile(r"\b(E\d{3})\b", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\b(?:q([1-4])\s*(20\d{2})|(20\d{2})\s*[-/]?\s*q([1-4]))\b", re.IGNORECASE)

_PREVIOUS_PERIOD = {
    "2026-Q1": None,
    "2026-Q2": "2026-Q1",
    "2026-Q3": "2026-Q2",
    "2026-Q4": "2026-Q3",
}


def previous_review_period(review_period: str) -> str | None:
    return _PREVIOUS_PERIOD.get(review_period)


def parse_performance_request(user_request: str) -> dict[str, Any]:
    """Extract performance analysis scope from a business request."""

    text = user_request.strip()
    lowered = text.lower()
    employee_id = None
    match = _EMPLOYEE_ID_RE.search(text)
    if match:
        employee_id = match.group(1).upper()

    review_period = "2026-Q2"
    period_label = "Q2 2026"
    quarter_match = _QUARTER_RE.search(text)
    if quarter_match:
        if quarter_match.group(1) and quarter_match.group(2):
            quarter = int(quarter_match.group(1))
            year = int(quarter_match.group(2))
        else:
            year = int(quarter_match.group(3))
            quarter = int(quarter_match.group(4))
        review_period = f"{year:04d}-Q{quarter}"
        period_label = f"Q{quarter} {year}"

    scan_support = any(
        token in lowered
        for token in (
            "need performance support",
            "needs performance support",
            "performance support",
            "identify employees",
            "employees who need",
            "performance issue",
            "performance issues",
        )
    ) and employee_id is None

    if any(token in lowered for token in ("improvement plan", "pip", "development plan")):
        operation = "improvement_plan"
    elif any(token in lowered for token in ("recommend", "recommendation")):
        operation = "recommend"
    elif scan_support:
        operation = "identify_support"
    elif "review" in lowered:
        operation = "review"
    else:
        operation = "analyze"

    return {
        "employee_id": employee_id,
        "review_period": review_period,
        "period_label": period_label,
        "previous_period": previous_review_period(review_period),
        "scan_support": scan_support or (operation == "identify_support"),
        "operation": operation,
        "query": text,
        "wants_performance": any(
            token in lowered
            for token in (
                "performance",
                "appraisal",
                "kpi",
                "goal",
                "improvement plan",
                "performance review",
                "performance report",
            )
        ),
    }
