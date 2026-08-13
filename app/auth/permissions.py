"""Deterministic development RBAC rules (not production-grade enterprise IAM)."""

from __future__ import annotations

import re
from typing import Any

from app.auth.models import Role, User
from app.api.errors import APIError
from app.workflows.contracts import WorkflowResult

_EMPLOYEE_ID_RE = re.compile(r"\bE\d{3,}\b", re.IGNORECASE)

# Who may approve/reject paused workflows in the API layer (Module 5B).
APPROVER_ROLES = frozenset({Role.MANAGER, Role.HR, Role.ADMIN})

# Roles that may run administrative / cross-employee workflow types freely.
CROSS_EMPLOYEE_ROLES = frozenset({Role.MANAGER, Role.HR, Role.ADMIN})

# Workflow types employees may initiate for themselves.
EMPLOYEE_ALLOWED_WORKFLOW_TYPES = frozenset(
    {
        "leave_attendance",
        "attendance",
        "training",
        "onboarding",
        "hr_services",
        "performance",
    }
)


def auth_required_error(message: str = "Authentication is required.") -> APIError:
    return APIError(
        status_code=401,
        code="AUTHENTICATION_REQUIRED",
        message=message,
    )


def forbidden_error(
    message: str = "You do not have permission to perform this action.",
) -> APIError:
    return APIError(
        status_code=403,
        code="FORBIDDEN",
        message=message,
    )


def extract_employee_ids(text: str) -> list[str]:
    return [match.upper() for match in _EMPLOYEE_ID_RE.findall(text or "")]


def assert_can_run_workflow(user: User, *, request_text: str, workflow_type: str | None) -> None:
    """Enforce employee self-service limits before WorkflowEngine.run()."""

    if user.role in CROSS_EMPLOYEE_ROLES:
        return

    if user.role != Role.EMPLOYEE:
        raise forbidden_error()

    if workflow_type and workflow_type not in EMPLOYEE_ALLOWED_WORKFLOW_TYPES:
        raise forbidden_error(
            f"Employees cannot run workflow type '{workflow_type}'."
        )

    # Recruitment / offboarding are staff-only even without an explicit type.
    lowered = (request_text or "").lower()
    if any(
        hint in lowered
        for hint in (
            "recruit",
            "candidate",
            "job opening",
            "shortlist",
            "offboard",
            "exit process",
        )
    ):
        raise forbidden_error("Employees cannot run recruitment or offboarding workflows.")

    own = (user.employee_id or "").upper()
    if not own:
        raise forbidden_error("Employee account is missing employee_id binding.")

    mentioned = extract_employee_ids(request_text)
    for employee_id in mentioned:
        if employee_id != own:
            raise forbidden_error(
                "Employees may only operate on their own employee record."
            )


def employee_run_entities(user: User) -> dict[str, Any] | None:
    if user.role == Role.EMPLOYEE and user.employee_id:
        return {"employee_id": user.employee_id}
    return None


def assert_can_view_workflow(user: User, result: WorkflowResult) -> None:
    state = result.state or {}
    result_org = str(state.get("organization_id") or "")
    if result_org != user.organization_id:
        # Callers should already 404 on org mismatch; keep a hard stop.
        raise forbidden_error()

    if user.role in CROSS_EMPLOYEE_ROLES:
        return

    if user.role != Role.EMPLOYEE:
        raise forbidden_error()

    initiator = str(state.get("user_id") or "")
    if initiator == user.user_id:
        return

    entities = state.get("entities") or {}
    employee_data = state.get("employee_data") or {}
    target = str(
        entities.get("employee_id")
        or employee_data.get("employee_id")
        or ""
    ).upper()
    own = (user.employee_id or "").upper()
    if own and target == own:
        return
    raise forbidden_error("Employees may only view their own workflow runs.")


def assert_can_approve(user: User, result: WorkflowResult) -> None:
    state = result.state or {}
    if str(state.get("organization_id") or "") != user.organization_id:
        raise forbidden_error()
    if user.role not in APPROVER_ROLES:
        raise forbidden_error("Your role is not permitted to approve or reject workflows.")

    metadata = state.get("metadata") or {}
    approval = metadata.get("approval") if isinstance(metadata, dict) else None
    required_role = ""
    if isinstance(approval, dict):
        required_role = str(approval.get("required_role") or "").strip().lower()

    # Platform checkpoints currently advertise "manager"; HR and admin may also act.
    if required_role in {"", "manager"}:
        return
    if required_role == "hr" and user.role in {Role.HR, Role.ADMIN}:
        return
    if required_role == "admin" and user.role == Role.ADMIN:
        return
    if user.role == Role.ADMIN:
        return
    raise forbidden_error(
        f"Role '{user.role.value}' cannot satisfy required approver '{required_role}'."
    )


def filter_results_for_user(
    user: User,
    items: list[WorkflowResult],
) -> list[WorkflowResult]:
    visible: list[WorkflowResult] = []
    for item in items:
        try:
            assert_can_view_workflow(user, item)
        except APIError:
            continue
        visible.append(item)
    return visible
