"""Validate HR employee_id bindings for authenticated organization users."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.auth.models import Role
from app.database.models.user import UserRecord
from app.database.repositories.user import UserRepository
from app.services.hr_store import get_hr_store

_DEFAULT_EMPLOYEE_ORG = "demo-org"


def normalize_employee_id(value: str | None) -> str | None:
    cleaned = (value or "").strip().upper()
    return cleaned or None


def _employee_organization_id(employee: dict) -> str:
    return str(employee.get("organization_id") or _DEFAULT_EMPLOYEE_ORG)


def directory_employee_public(employee: dict) -> dict[str, str | None]:
    return {
        "employee_id": str(employee.get("employee_id") or ""),
        "name": str(employee.get("name") or ""),
        "department": str(employee.get("department") or "") or None,
        "job_role": str(employee.get("role") or "") or None,
        "employment_status": str(employee.get("employment_status") or "") or None,
    }


def get_organization_employee(organization_id: str, employee_id: str) -> dict | None:
    record = get_hr_store().get_employee(employee_id, organization_id=organization_id)
    if record is None:
        return None
    if _employee_organization_id(record) != organization_id:
        return None
    return record


def find_bound_user(
    repo: UserRepository,
    *,
    organization_id: str,
    employee_id: str,
    exclude_user_id: str | None = None,
) -> UserRecord | None:
    key = normalize_employee_id(employee_id)
    if not key:
        return None
    return repo.find_binding(
        organization_id,
        key,
        exclude_user_id=exclude_user_id,
    )


def assert_employee_bindable(
    db: Session,
    *,
    organization_id: str,
    employee_id: str | None,
    required: bool,
    exclude_user_id: str | None = None,
) -> str | None:
    """Return a normalized employee_id or None. Rejects untrusted/arbitrary IDs."""

    normalized = normalize_employee_id(employee_id)
    if not normalized:
        if required:
            raise APIError(
                status_code=400,
                code="EMPLOYEE_BINDING_REQUIRED",
                message="Select an employee record to bind this account.",
            )
        return None

    record = get_organization_employee(organization_id, normalized)
    if record is None:
        raise APIError(
            status_code=400,
            code="EMPLOYEE_NOT_FOUND",
            message="Employee record was not found in this organization.",
        )
    status = str(record.get("employment_status") or "").strip().lower()
    if status and status != "active":
        raise APIError(
            status_code=400,
            code="EMPLOYEE_NOT_ELIGIBLE",
            message="That employee record is not eligible for account binding.",
        )

    bound = find_bound_user(
        UserRepository(db),
        organization_id=organization_id,
        employee_id=normalized,
        exclude_user_id=exclude_user_id,
    )
    if bound is not None:
        raise APIError(
            status_code=409,
            code="EMPLOYEE_ALREADY_BOUND",
            message="This employee record is already bound to another user account.",
        )
    return normalized


def list_organization_directory(db: Session, organization_id: str) -> list[dict]:
    repo = UserRepository(db)
    bindings = {
        (item.employee_id or "").strip().upper(): item
        for item in repo.list_bindings(organization_id)
        if item.employee_id
    }
    directory: list[dict] = []
    for employee in get_hr_store().list_employees(organization_id=organization_id):
        if _employee_organization_id(employee) != organization_id:
            continue
        public = directory_employee_public(employee)
        employee_id = str(public["employee_id"] or "").upper()
        bound = bindings.get(employee_id)
        public["bound_user_id"] = bound.user_id if bound else None
        public["bound_username"] = bound.username if bound else None
        public["available"] = bound is None
        directory.append(public)
    return directory


def binding_required_for_role(role: Role) -> bool:
    return role == Role.EMPLOYEE
