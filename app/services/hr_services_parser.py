"""Parse HR services requests into employee, category hints, and operation scope."""

from __future__ import annotations

import re
from typing import Any

_EMPLOYEE_ID_RE = re.compile(r"\b(E\d{3})\b", re.IGNORECASE)
_CANDIDATE_ID_RE = re.compile(r"\b(C\d{3})\b", re.IGNORECASE)
_MONTH_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)

MONTH_TO_RANGE = {
    "january": ("2026-01-01", "2026-01-31"),
    "february": ("2026-02-01", "2026-02-28"),
    "march": ("2026-03-01", "2026-03-31"),
    "april": ("2026-04-01", "2026-04-30"),
    "may": ("2026-05-01", "2026-05-31"),
    "june": ("2026-06-01", "2026-06-30"),
    "july": ("2026-07-01", "2026-07-31"),
    "august": ("2026-08-01", "2026-08-31"),
    "september": ("2026-09-01", "2026-09-30"),
    "october": ("2026-10-01", "2026-10-31"),
    "november": ("2026-11-01", "2026-11-30"),
    "december": ("2026-12-01", "2026-12-31"),
}

SERVICE_CATEGORIES = (
    "leave_balance",
    "attendance",
    "employment_document",
    "policy_information",
    "benefits",
    "employee_profile",
    "payroll_routing",
    "training",
    "onboarding",
    "recruitment_status",
    "general_hr",
)


def classify_hr_service_category(user_request: str) -> str:
    """Deterministic category classification (not LLM-only routing)."""

    lowered = user_request.strip().lower()

    if any(
        token in lowered
        for token in (
            "employment certificate",
            "experience letter",
            "employment verification",
            "verification letter",
            "hr document",
        )
    ):
        return "employment_document"

    if any(
        token in lowered
        for token in (
            "payroll",
            "salary issue",
            "salary information looks incorrect",
            "pay slip",
            "paycheck",
        )
    ):
        return "payroll_routing"

    if any(
        token in lowered
        for token in (
            "update my phone",
            "update phone",
            "phone number",
            "profile update",
            "change my address",
            "update my address",
            "employee profile",
        )
    ):
        return "employee_profile"

    if any(
        token in lowered
        for token in (
            "benefit",
            "benefits",
            "health insurance",
            "medical coverage",
        )
    ):
        return "benefits"

    if any(
        token in lowered
        for token in (
            "leave balance",
            "how many annual leave",
            "how much annual leave",
            "annual leave days",
            "remaining leave",
            "pto balance",
        )
    ):
        return "leave_balance"

    if any(
        token in lowered
        for token in (
            "attendance summary",
            "attendance inquiry",
            "my attendance",
            "show my attendance",
            "attendance for",
        )
    ) and "policy" not in lowered:
        return "attendance"

    if any(
        token in lowered
        for token in (
            "attendance policy",
            "leave policy",
            "policy question",
            "hr policy",
            "what is the",
            "explain the",
        )
    ) and any(
        token in lowered
        for token in ("policy", "maternity", "handbook")
    ):
        return "policy_information"

    if "policy" in lowered and any(
        token in lowered for token in ("attendance", "leave", "hr", "maternity")
    ):
        return "policy_information"

    if any(
        token in lowered
        for token in (
            "training program",
            "training programs",
            "training information",
            "available training",
            "what training",
        )
    ):
        return "training"

    if any(
        token in lowered
        for token in (
            "onboarding status",
            "status of onboarding",
            "onboarding for",
            "my onboarding",
        )
    ):
        return "onboarding"

    if any(
        token in lowered
        for token in (
            "recruitment status",
            "candidate status",
            "status for candidate",
            "check recruitment",
        )
    ) or _CANDIDATE_ID_RE.search(user_request):
        return "recruitment_status"

    if any(
        token in lowered
        for token in (
            "hr ticket",
            "hr support",
            "hr request",
            "hr service",
            "general hr",
            "help from hr",
        )
    ):
        return "general_hr"

    return "general_hr"


def parse_hr_services_request(user_request: str) -> dict[str, Any]:
    """Extract HR services request scope from a business request."""

    text = user_request.strip()
    lowered = text.lower()
    employee_id = None
    match = _EMPLOYEE_ID_RE.search(text)
    if match:
        employee_id = match.group(1).upper()

    candidate_id = None
    candidate_match = _CANDIDATE_ID_RE.search(text)
    if candidate_match:
        candidate_id = candidate_match.group(1).upper()

    category = classify_hr_service_category(text)

    document_type = None
    if "experience letter" in lowered:
        document_type = "experience_letter"
    elif "employment verification" in lowered or "verification letter" in lowered:
        document_type = "employment_verification"
    elif "employment certificate" in lowered or category == "employment_document":
        document_type = "employment_certificate"

    leave_type = "annual"
    if "sick" in lowered:
        leave_type = "sick"

    start_date = "2026-07-01"
    end_date = "2026-07-31"
    month_match = _MONTH_RE.search(text)
    if month_match:
        start_date, end_date = MONTH_TO_RANGE[month_match.group(1).lower()]

    operation = "inquire"
    if category in {"employment_document", "employee_profile", "payroll_routing", "general_hr"}:
        operation = "request"
    if "ticket" in lowered or "support" in lowered:
        operation = "support"

    return {
        "employee_id": employee_id,
        "candidate_id": candidate_id,
        "category": category,
        "operation": operation,
        "document_type": document_type,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "query": text,
        "summary": text[:240],
    }
