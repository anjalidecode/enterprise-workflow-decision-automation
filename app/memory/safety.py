"""Allowlist and sanitization for long-term memory writes.

Structured policy/tools remain authoritative. Long-term memory stores only
compact workflow facts for future context — never secrets or raw payloads.
"""

from __future__ import annotations

from typing import Any

from app.memory.errors import MemorySafetyError

ALLOWED_LONG_TERM_FIELDS = frozenset(
    {
        "organization_id",
        "user_id",
        "employee_id",
        "job_id",
        "candidate_id",
        "shortlisted_count",
        "workflow_type",
        "outcome",
        "days",
        "start_date",
        "rationale_summary",
        "requires_human_approval",
        "workflow_id",
        "timestamp",
    }
)

_SECRET_MARKERS = ("api_key", "secret", "password", "token", "authorization")
_FORBIDDEN_KEYS = frozenset(
    {
        "tool_payload",
        "tool_payloads",
        "notification",
        "notification_body",
        "message",
        "employee_data",
        "leave_balances",
        "google_api_key",
        "access_token",
        "refresh_token",
    }
)


def _is_forbidden_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _FORBIDDEN_KEYS:
        return True
    return any(marker in lowered for marker in _SECRET_MARKERS)


def sanitize_long_term_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep allowlisted fields only. Reject secrets, tool payloads, and notification bodies."""

    forbidden = sorted(key for key in payload if _is_forbidden_key(key))
    if forbidden:
        raise MemorySafetyError(
            "Long-term memory refused disallowed fields: " + ", ".join(forbidden)
        )

    cleaned: dict[str, Any] = {}
    for key in ALLOWED_LONG_TERM_FIELDS:
        if key not in payload or payload[key] is None:
            continue
        value = payload[key]
        if key == "rationale_summary":
            cleaned[key] = str(value)[:400]
        elif key == "days":
            cleaned[key] = int(value)
        elif key == "shortlisted_count":
            cleaned[key] = int(value)
        elif key == "requires_human_approval":
            cleaned[key] = bool(value)
        elif key in {
            "organization_id",
            "user_id",
            "employee_id",
            "workflow_id",
            "job_id",
            "candidate_id",
        }:
            cleaned[key] = str(value)
        else:
            cleaned[key] = value
    return cleaned
