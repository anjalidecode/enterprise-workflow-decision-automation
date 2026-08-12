"""Typed payloads used by the leave & attendance workflow."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.decision import WorkflowDecision


class LeaveRequest(BaseModel):
    """Parsed leave request extracted from a user request."""

    employee_id: str | None = None
    days: int | None = None
    start_date: str | None = None
    leave_type: str = "annual"


class LeaveDecision(WorkflowDecision):
    """Leave-specific decision. Extends the reusable WorkflowDecision contract."""

    employee_id: str | None = None
    requested_days: int | None = None
    leave_type: str = "annual"
