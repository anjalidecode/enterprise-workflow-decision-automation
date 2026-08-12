"""Service interfaces (ports). Tools depend on these, not on storage backends.

Current implementations are in-memory. Later they can be swapped for PostgreSQL
or external HR/email APIs without changing ToolExecutor or agents.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class HREmployeeService(Protocol):
    """Employee and leave-balance lookups for any workflow domain."""

    def get_employee(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any] | None: ...

    def get_leave_balance(
        self,
        employee_id: str,
        leave_type: str = "annual",
        *,
        organization_id: str = "",
    ) -> int | None: ...

    def get_leave_policy(self, *, organization_id: str = "") -> dict[str, Any]: ...

    def update_leave_balance(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        days: int,
        leave_type: str = "annual",
        start_date: str | None = None,
        organization_id: str = "",
    ) -> dict[str, Any]: ...


@runtime_checkable
class NotificationServicePort(Protocol):
    """Notification delivery port. Implementations may be inbox, email, SMS, webhook."""

    def send(
        self,
        *,
        employee_id: str,
        message: str,
        workflow_id: str,
        organization_id: str = "",
        channel: str = "simulated_inbox",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]: ...

    def log_fallback(
        self,
        *,
        employee_id: str,
        message: str,
        workflow_id: str,
        organization_id: str = "",
    ) -> dict[str, Any]: ...
