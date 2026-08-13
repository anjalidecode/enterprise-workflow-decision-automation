"""In-memory simulated HR system, seeded from JSON. JSON files are never written.

This is the development implementation of HREmployeeService. Later it can be
replaced with a PostgreSQL or external HRIS adapter behind the same interface.
"""

from __future__ import annotations

import copy
from typing import Any

from app.services.errors import SimulatedServiceError
from app.services.hr_data import load_employees, load_leave_policy
from app.tools.idempotency import build_idempotency_key


def _employee_key(employee_id: str) -> str:
    return employee_id.strip().upper()


def _org_matches(employee: dict[str, Any], organization_id: str) -> bool:
    """Empty organization_id matches the current single-tenant seed data."""

    if not organization_id:
        return True
    employee_org = str(employee.get("organization_id") or "")
    return employee_org in {"", organization_id}


class SimulatedHRStore:
    """Mutable HR records for workflow runs. Reset between tests/runs."""

    def __init__(self) -> None:
        self._employees: dict[str, dict[str, Any]] = {}
        self._policy: dict[str, Any] = {}
        self._applied_leave_updates: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        """Reload seed JSON into memory and clear runtime side effects."""

        self._employees = {
            _employee_key(str(employee["employee_id"])): copy.deepcopy(employee)
            for employee in load_employees()
        }
        self._policy = copy.deepcopy(load_leave_policy())
        self._applied_leave_updates = {}
        self._faults = {}

    def inject_error(self, operation: str, times: int = 1) -> None:
        """Test helper: next N calls to operation raise a retryable service error."""

        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated HR service error during {operation}.")

    def get_employee(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any] | None:
        self._maybe_fault("get_employee")
        employee = self._employees.get(_employee_key(employee_id))
        if employee is None or not _org_matches(employee, organization_id):
            return None
        return copy.deepcopy(employee)

    def list_employees(self, *, organization_id: str = "") -> list[dict[str, Any]]:
        """Return employee directory copies, optionally filtered by organization."""

        self._maybe_fault("list_employees")
        results: list[dict[str, Any]] = []
        for employee in self._employees.values():
            if not _org_matches(employee, organization_id):
                continue
            results.append(copy.deepcopy(employee))
        results.sort(key=lambda item: str(item.get("employee_id") or ""))
        return results

    def get_leave_balance(
        self,
        employee_id: str,
        leave_type: str = "annual",
        *,
        organization_id: str = "",
    ) -> int | None:
        self._maybe_fault("get_leave_balance")
        employee = self._employees.get(_employee_key(employee_id))
        if employee is None or not _org_matches(employee, organization_id):
            return None
        balances = employee.get("leave_balances") or {}
        if leave_type not in balances:
            return None
        return int(balances[leave_type])

    def get_leave_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_leave_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy["organization_id"] = organization_id
        return policy

    def update_leave_balance(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        days: int,
        leave_type: str = "annual",
        start_date: str | None = None,
        organization_id: str = "",
    ) -> dict[str, Any]:
        """Deduct leave. Idempotent for the same org/workflow request key."""

        self._maybe_fault("update_leave_balance")
        key = build_idempotency_key(
            capability="leave.balance.update",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            leave_type=leave_type,
            days=days,
            start_date=start_date or "",
        )
        if key in self._applied_leave_updates:
            replay = copy.deepcopy(self._applied_leave_updates[key])
            replay["idempotent_replay"] = True
            return replay

        stored = self._employees.get(_employee_key(employee_id))
        if stored is None or not _org_matches(stored, organization_id):
            raise KeyError(f"Employee {employee_id} was not found in the HR store.")

        balances = dict(stored.get("leave_balances") or {})
        previous = int(balances.get(leave_type, 0))
        new_balance = previous - int(days)
        balances[leave_type] = new_balance
        stored["leave_balances"] = balances

        result = {
            "employee_id": stored["employee_id"],
            "leave_type": leave_type,
            "days": days,
            "previous_balance": previous,
            "new_balance": new_balance,
            "idempotent_replay": False,
            "organization_id": organization_id,
            "source": "simulated_hr_store",
        }
        self._applied_leave_updates[key] = copy.deepcopy(result)
        return copy.deepcopy(result)


_STORE: SimulatedHRStore | None = None


def get_hr_store() -> SimulatedHRStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedHRStore()
    return _STORE


def reset_hr_store() -> SimulatedHRStore:
    store = get_hr_store()
    store.reset()
    return store
