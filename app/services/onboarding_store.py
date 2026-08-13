"""In-memory onboarding store: documents, profiles, tasks, equipment, access.

JSON seeds are loaded once per reset and never written back.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError
from app.services.onboarding_data import (
    load_onboarding_documents,
    load_onboarding_policy,
    load_onboarding_profiles,
)
from app.tools.idempotency import build_idempotency_key


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _employee_key(employee_id: str) -> str:
    return employee_id.strip().upper()


def _org_matches(record: dict[str, Any], organization_id: str) -> bool:
    if not organization_id:
        return True
    record_org = str(record.get("organization_id") or "")
    return record_org in {"", organization_id}


class SimulatedOnboardingStore:
    """Mutable onboarding records for workflow runs."""

    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []
        self._profiles: dict[str, dict[str, Any]] = {}
        self._policy: dict[str, Any] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._equipment: dict[str, dict[str, Any]] = {}
        self._access: dict[str, dict[str, Any]] = {}
        self._statuses: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        self._documents = [copy.deepcopy(item) for item in load_onboarding_documents()]
        self._profiles = {
            _employee_key(str(item["employee_id"])): copy.deepcopy(item)
            for item in load_onboarding_profiles()
        }
        self._policy = copy.deepcopy(load_onboarding_policy())
        self._tasks = {}
        self._equipment = {}
        self._access = {}
        self._statuses = {}
        self._faults = {}

    def inject_error(self, operation: str, times: int = 1) -> None:
        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated onboarding error during {operation}.")

    def get_profile(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any] | None:
        self._maybe_fault("get_profile")
        profile = self._profiles.get(_employee_key(employee_id))
        if profile is None or not _org_matches(profile, organization_id):
            return None
        return copy.deepcopy(profile)

    def list_documents(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("list_documents")
        results: list[dict[str, Any]] = []
        for item in self._documents:
            if _employee_key(str(item.get("employee_id") or "")) != _employee_key(employee_id):
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        return results

    def verify_documents(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("verify_documents")
        policy = self.get_policy(organization_id=organization_id)
        mandatory = list(policy.get("mandatory_documents") or [])
        documents = self.list_documents(employee_id, organization_id=organization_id)
        by_type = {str(item.get("document_type")): item for item in documents}

        verified: list[str] = []
        missing: list[str] = []
        invalid: list[str] = []
        findings: list[dict[str, Any]] = []

        for doc_type in mandatory:
            item = by_type.get(doc_type)
            if item is None or str(item.get("status") or "") == "missing":
                missing.append(doc_type)
                findings.append(
                    {
                        "document_type": doc_type,
                        "status": "missing",
                        "verified": False,
                    }
                )
                continue
            if not bool(item.get("verified")) or str(item.get("status") or "") == "invalid":
                invalid.append(doc_type)
                findings.append(
                    {
                        "document_type": doc_type,
                        "status": str(item.get("status") or "invalid"),
                        "verified": False,
                        "submitted_at": item.get("submitted_at"),
                    }
                )
                continue
            verified.append(doc_type)
            findings.append(
                {
                    "document_type": doc_type,
                    "status": str(item.get("status") or "submitted"),
                    "verified": True,
                    "submitted_at": item.get("submitted_at"),
                }
            )

        return {
            "employee_id": _employee_key(employee_id),
            "mandatory_documents": mandatory,
            "verified_documents": verified,
            "missing_documents": missing,
            "invalid_documents": invalid,
            "all_mandatory_verified": len(missing) == 0 and len(invalid) == 0,
            "findings": findings,
            "source": "simulated_onboarding_store",
        }

    def get_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy["organization_id"] = organization_id
        return policy

    def validate_onboarding_policy(
        self,
        *,
        employee: dict[str, Any],
        document_verification: dict[str, Any],
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("validate_onboarding_policy")
        policy = self.get_policy(organization_id=organization_id)
        rules = dict(policy.get("rules") or {})
        profile = self.get_profile(
            str(employee.get("employee_id") or ""),
            organization_id=organization_id,
        ) or {}

        violations: list[str] = []
        warnings: list[str] = []

        if rules.get("employee_must_be_active") and employee.get("employment_status") != "active":
            violations.append("Employee must be active to start onboarding.")
        if rules.get("manager_required") and not employee.get("manager"):
            violations.append("Manager assignment is required for onboarding.")
        if rules.get("joining_date_required") and not employee.get("joining_date"):
            violations.append("Joining date is required for onboarding.")
        if rules.get("all_mandatory_documents_verified") and not document_verification.get(
            "all_mandatory_verified"
        ):
            missing = document_verification.get("missing_documents") or []
            invalid = document_verification.get("invalid_documents") or []
            if missing:
                violations.append(
                    "Missing mandatory documents: " + ", ".join(str(item) for item in missing)
                )
            if invalid:
                violations.append(
                    "Invalid mandatory documents: " + ", ".join(str(item) for item in invalid)
                )

        privileged = list(profile.get("privileged_access_required") or [])
        known_privileged = {
            str(item).lower() for item in (policy.get("privileged_access") or [])
        }
        privileged_requested = [
            item for item in privileged if str(item).lower() in known_privileged
        ]
        requires_human_approval = bool(privileged_requested) and bool(
            rules.get("privileged_access_requires_human_approval")
        )
        if privileged_requested:
            warnings.append(
                "Privileged access requested: "
                + ", ".join(str(item) for item in privileged_requested)
            )

        eligible = len(violations) == 0
        return {
            "policy_id": policy.get("policy_id"),
            "eligible": eligible,
            "violations": violations,
            "warnings": warnings,
            "requires_human_approval": requires_human_approval,
            "mandatory_tasks": list(policy.get("mandatory_tasks") or []),
            "standard_equipment": list(policy.get("standard_equipment") or []),
            "standard_system_access": list(policy.get("standard_system_access") or []),
            "equipment_required": list(profile.get("equipment_required") or []),
            "access_required": list(profile.get("access_required") or []),
            "privileged_access_required": privileged_requested,
            "onboarding_track": profile.get("onboarding_track"),
            "source": "simulated_onboarding_store",
        }

    def create_task(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        task_type: str,
        organization_id: str = "",
        assignee: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_task")
        key = build_idempotency_key(
            capability="onboarding.task.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            task_type=task_type,
        )
        if key in self._tasks:
            replay = copy.deepcopy(self._tasks[key])
            replay["idempotent_replay"] = True
            return replay

        record = {
            "task_id": f"TASK-{len(self._tasks) + 1:04d}",
            "employee_id": _employee_key(employee_id),
            "task_type": task_type,
            "assignee": assignee or "HR-ONBOARDING",
            "status": "created",
            "organization_id": organization_id,
            "workflow_id": workflow_id,
            "created_at": _utc_now(),
            "idempotent_replay": False,
            "source": "simulated_onboarding_store",
        }
        self._tasks[key] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def list_tasks(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
        workflow_id: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("list_tasks")
        results: list[dict[str, Any]] = []
        for item in self._tasks.values():
            if _employee_key(str(item.get("employee_id") or "")) != _employee_key(employee_id):
                continue
            if organization_id and str(item.get("organization_id") or "") not in {
                "",
                organization_id,
            }:
                continue
            if workflow_id and str(item.get("workflow_id") or "") != workflow_id:
                continue
            results.append(copy.deepcopy(item))
        return results

    def request_equipment(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        item: str,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("request_equipment")
        key = build_idempotency_key(
            capability="onboarding.equipment.request",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            item=item,
        )
        if key in self._equipment:
            replay = copy.deepcopy(self._equipment[key])
            replay["idempotent_replay"] = True
            return replay

        record = {
            "request_id": f"EQ-{len(self._equipment) + 1:04d}",
            "employee_id": _employee_key(employee_id),
            "item": item,
            "status": "requested",
            "organization_id": organization_id,
            "workflow_id": workflow_id,
            "requested_at": _utc_now(),
            "idempotent_replay": False,
            "source": "simulated_onboarding_store",
        }
        self._equipment[key] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def request_access(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        system: str,
        organization_id: str = "",
        privileged: bool = False,
    ) -> dict[str, Any]:
        self._maybe_fault("request_access")
        key = build_idempotency_key(
            capability="onboarding.access.request",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            system=system,
        )
        if key in self._access:
            replay = copy.deepcopy(self._access[key])
            replay["idempotent_replay"] = True
            return replay

        record = {
            "request_id": f"ACC-{len(self._access) + 1:04d}",
            "employee_id": _employee_key(employee_id),
            "system": system,
            "privileged": privileged,
            "status": "requested",
            "organization_id": organization_id,
            "workflow_id": workflow_id,
            "requested_at": _utc_now(),
            "idempotent_replay": False,
            "source": "simulated_onboarding_store",
        }
        self._access[key] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def update_status(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        status: str,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("update_status")
        key = build_idempotency_key(
            capability="onboarding.status.update",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            status=status,
        )
        if key in self._statuses:
            replay = copy.deepcopy(self._statuses[key])
            replay["idempotent_replay"] = True
            return replay

        record = {
            "employee_id": _employee_key(employee_id),
            "status": status,
            "organization_id": organization_id,
            "workflow_id": workflow_id,
            "updated_at": _utc_now(),
            "idempotent_replay": False,
            "source": "simulated_onboarding_store",
        }
        self._statuses[key] = copy.deepcopy(record)
        return copy.deepcopy(record)


_STORE: SimulatedOnboardingStore | None = None


def get_onboarding_store() -> SimulatedOnboardingStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedOnboardingStore()
    return _STORE


def reset_onboarding_store() -> SimulatedOnboardingStore:
    store = get_onboarding_store()
    store.reset()
    return store
