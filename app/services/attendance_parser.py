"""Parse attendance requests into employee/department/date-range scope."""

from __future__ import annotations

import calendar
import re
from typing import Any

_EMPLOYEE_ID_RE = re.compile(r"\b(E\d{3})\b", re.IGNORECASE)
_MONTH_YEAR_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+(20\d{2})\b",
    re.IGNORECASE,
)
_ISO_RANGE_RE = re.compile(
    r"\b(20\d{2}-\d{2}-\d{2})\s*(?:to|through|-)\s*(20\d{2}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_DEPARTMENTS = ("engineering", "finance", "marketing", "hr", "sales")

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def parse_attendance_request(user_request: str) -> dict[str, Any]:
    """Extract attendance analysis scope from a business request."""

    text = user_request.strip()
    lowered = text.lower()
    employee_id = None
    match = _EMPLOYEE_ID_RE.search(text)
    if match:
        employee_id = match.group(1).upper()

    department = None
    for name in _DEPARTMENTS:
        if name in lowered:
            department = name.title()
            break

    start_date = "2026-07-01"
    end_date = "2026-07-31"
    month_label = "July 2026"

    range_match = _ISO_RANGE_RE.search(text)
    month_match = _MONTH_YEAR_RE.search(text)
    if range_match:
        start_date = range_match.group(1)
        end_date = range_match.group(2)
        month_label = f"{start_date} to {end_date}"
    elif month_match:
        month_name = month_match.group(1).lower()
        year = int(month_match.group(2))
        month = _MONTHS[month_name]
        last_day = calendar.monthrange(year, month)[1]
        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
        month_label = f"{month_name.title()} {year}"
    elif "this month" in lowered:
        start_date = "2026-07-01"
        end_date = "2026-07-31"
        month_label = "July 2026"

    scan_issues = any(
        token in lowered
        for token in (
            "attendance issues",
            "find employees",
            "employees with",
            "attendance report",
            "department",
        )
    ) and employee_id is None

    return {
        "employee_id": employee_id,
        "department": department,
        "start_date": start_date,
        "end_date": end_date,
        "month_label": month_label,
        "scan_issues": scan_issues or (department is not None and employee_id is None),
        "query": text,
        "wants_attendance": any(
            token in lowered
            for token in (
                "attendance",
                "absent",
                "absence",
                "late",
                "lateness",
                "present days",
                "attendance record",
                "attendance report",
                "attendance issue",
            )
        ),
    }
