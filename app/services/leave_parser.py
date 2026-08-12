"""Deterministic parsing of leave requests from natural-language text."""

from __future__ import annotations

import re

from app.models.leave import LeaveRequest

EMPLOYEE_ID_PATTERN = re.compile(r"\b(E\d{3,})\b", re.IGNORECASE)
DAYS_PATTERN = re.compile(r"\b(\d+)\s*days?\b", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def parse_leave_request(text: str) -> LeaveRequest:
    """Extract employee id, day count, and start date from a request string."""

    employee_match = EMPLOYEE_ID_PATTERN.search(text)
    days_match = DAYS_PATTERN.search(text)
    date_match = DATE_PATTERN.search(text)

    days = int(days_match.group(1)) if days_match else None
    return LeaveRequest(
        employee_id=employee_match.group(1).upper() if employee_match else None,
        days=days,
        start_date=date_match.group(1) if date_match else None,
        leave_type="annual",
    )
