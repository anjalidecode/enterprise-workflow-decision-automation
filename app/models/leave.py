"""Typed payloads used by the leave & attendance workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LeaveRequest(BaseModel):
    """Parsed leave request extracted from a user request."""

    employee_id: str | None = None
    days: int | None = None
    start_date: str | None = None
    leave_type: str = "annual"


class LeaveDecision(BaseModel):
    """Structured decision produced by the Decision Agent."""

    outcome: Literal["approve", "reject", "pending_approval"]
    rationale: str
    executable: bool
    employee_id: str | None = None
    requested_days: int | None = None
    leave_type: str = "annual"
    confidence: float = Field(ge=0.0, le=1.0)
