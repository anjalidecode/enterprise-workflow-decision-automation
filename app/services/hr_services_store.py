"""In-memory HR services store: tickets, documents, routing, policy.

JSON seeds are loaded once per reset and never written back.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError
from app.services.hr_services_data import load_hr_service_requests, load_hr_services_policy
from app.tools.idempotency import build_idempotency_key

HR_QUEUE_ID = "HR-QUEUE-001"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _employee_key(employee_id: str) -> str:
    return employee_id.strip().upper()


def _org_matches(record: dict[str, Any], organization_id: str) -> bool:
    if not organization_id:
        return True
    record_org = str(record.get("organization_id") or "")
    return record_org in {"", organization_id}


class SimulatedHRServicesStore:
    """Mutable HR service tickets/documents for workflow runs."""

    def __init__(self) -> None:
        self._requests: list[dict[str, Any]] = []
        self._policy: dict[str, Any] = {}
        self._created: dict[str, dict[str, Any]] = {}
        self._documents: dict[str, dict[str, Any]] = {}
        self._routes: dict[str, dict[str, Any]] = {}
        self._updates: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self._counter = 100
        self.reset()

    def reset(self) -> None:
        self._requests = [copy.deepcopy(item) for item in load_hr_service_requests()]
        self._policy = copy.deepcopy(load_hr_services_policy())
        self._created = {}
        self._documents = {}
        self._routes = {}
        self._updates = {}
        self._faults = {}
        self._counter = 100

    def inject_error(self, operation: str, times: int = 1) -> None:
        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated HR services error during {operation}.")

    def get_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy = {**policy, "organization_id": organization_id}
        return policy

    def get_request(
        self,
        request_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any] | None:
        self._maybe_fault("get_request")
        key = request_id.strip().upper()
        for item in list(self._created.values()) + self._requests:
            if str(item.get("request_id") or "").upper() != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if organization_id and str(item.get("organization_id") or "") == organization_id:
                return copy.deepcopy(item)
        for item in list(self._created.values()) + self._requests:
            if str(item.get("request_id") or "").upper() != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if not organization_id and str(item.get("organization_id") or ""):
                continue
            return copy.deepcopy(item)
        return None

    def list_requests(
        self,
        *,
        employee_id: str = "",
        organization_id: str = "",
        status: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("list_requests")
        emp_key = _employee_key(employee_id) if employee_id else ""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in list(self._created.values()) + self._requests:
            request_id = str(item.get("request_id") or "")
            if request_id in seen:
                continue
            if emp_key and _employee_key(str(item.get("employee_id") or "")) != emp_key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if organization_id:
                if str(item.get("organization_id") or "") not in {"", organization_id}:
                    continue
            elif str(item.get("organization_id") or ""):
                continue
            if status and str(item.get("status") or "") != status:
                continue
            seen.add(request_id)
            results.append(copy.deepcopy(item))
        results.sort(key=lambda row: str(row.get("request_id") or ""))
        return results

    def create_request(
        self,
        *,
        employee_id: str,
        category: str,
        summary: str,
        priority: str = "normal",
        status: str = "open",
        workflow_id: str = "",
        organization_id: str = "",
        document_type: str | None = None,
    ) -> dict[str, Any]:
        self._maybe_fault("create_request")
        key = build_idempotency_key(
            capability="hr_service.request.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=employee_id,
            category=category,
            summary=summary[:80],
        )
        existing = self._created.get(key)
        if existing:
            return {**copy.deepcopy(existing), "idempotent_replay": True}

        self._counter += 1
        record = {
            "request_id": f"HSR-{self._counter}",
            "organization_id": organization_id or "",
            "employee_id": _employee_key(employee_id),
            "category": category,
            "priority": priority,
            "summary": summary,
            "status": status,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "routed_to_hr": False,
            "document_type": document_type,
            "workflow_id": workflow_id,
            "source": "simulated_hr_services_store",
            "idempotent_replay": False,
        }
        self._created[key] = record
        return copy.deepcopy(record)

    def update_request(
        self,
        *,
        request_id: str,
        status: str,
        workflow_id: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("update_request")
        key = build_idempotency_key(
            capability="hr_service.request.update",
            workflow_id=workflow_id,
            organization_id=organization_id,
            request_id=request_id,
            status=status,
        )
        existing = self._updates.get(key)
        if existing:
            return {**copy.deepcopy(existing), "idempotent_replay": True}

        current = self.get_request(request_id, organization_id=organization_id)
        if current is None:
            raise SimulatedServiceError(f"HR service request {request_id} not found.")

        updated = {
            **current,
            "status": status,
            "updated_at": _utc_now(),
            "workflow_id": workflow_id or current.get("workflow_id"),
            "source": "simulated_hr_services_store",
            "idempotent_replay": False,
        }
        # Keep created/runtime map in sync when present.
        for map_key, item in list(self._created.items()):
            if str(item.get("request_id") or "").upper() == request_id.strip().upper():
                self._created[map_key] = updated
                break
        else:
            for idx, item in enumerate(self._requests):
                if str(item.get("request_id") or "").upper() == request_id.strip().upper():
                    self._requests[idx] = updated
                    break
        self._updates[key] = updated
        return copy.deepcopy(updated)

    def create_document_request(
        self,
        *,
        employee_id: str,
        document_type: str,
        workflow_id: str = "",
        organization_id: str = "",
        summary: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_document_request")
        key = build_idempotency_key(
            capability="hr_service.document.request",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=employee_id,
            document_type=document_type,
        )
        existing = self._documents.get(key)
        if existing:
            return {**copy.deepcopy(existing), "idempotent_replay": True}

        ticket = self.create_request(
            employee_id=employee_id,
            category="employment_document",
            summary=summary or f"Document request: {document_type}",
            priority="normal",
            status="open",
            workflow_id=workflow_id,
            organization_id=organization_id,
            document_type=document_type,
        )
        record = {
            "document_request_id": f"DOC-{ticket['request_id']}",
            "request_id": ticket["request_id"],
            "employee_id": _employee_key(employee_id),
            "document_type": document_type,
            "status": "requested",
            "organization_id": organization_id or "",
            "workflow_id": workflow_id,
            "created_at": _utc_now(),
            "source": "simulated_hr_services_store",
            "idempotent_replay": False,
        }
        self._documents[key] = record
        return copy.deepcopy(record)

    def route_to_hr(
        self,
        *,
        request_id: str,
        reason: str = "",
        workflow_id: str = "",
        organization_id: str = "",
        priority: str = "normal",
    ) -> dict[str, Any]:
        self._maybe_fault("route_to_hr")
        key = build_idempotency_key(
            capability="hr_service.route_to_hr",
            workflow_id=workflow_id,
            organization_id=organization_id,
            request_id=request_id,
            reason=reason[:80],
        )
        existing = self._routes.get(key)
        if existing:
            return {**copy.deepcopy(existing), "idempotent_replay": True}

        current = self.get_request(request_id, organization_id=organization_id)
        if current is None:
            raise SimulatedServiceError(f"HR service request {request_id} not found.")

        updated = self.update_request(
            request_id=request_id,
            status="escalated" if priority == "high" else "in_progress",
            workflow_id=workflow_id,
            organization_id=organization_id,
        )
        # Mark routed flag on the underlying record.
        for map_key, item in list(self._created.items()):
            if str(item.get("request_id") or "").upper() == request_id.strip().upper():
                item["routed_to_hr"] = True
                self._created[map_key] = item
                updated = item
                break
        else:
            for idx, item in enumerate(self._requests):
                if str(item.get("request_id") or "").upper() == request_id.strip().upper():
                    item["routed_to_hr"] = True
                    self._requests[idx] = item
                    updated = item
                    break

        record = {
            "routing_id": f"ROUTE-{request_id}",
            "request_id": request_id,
            "queue": HR_QUEUE_ID,
            "reason": reason,
            "priority": priority,
            "status": "routed",
            "organization_id": organization_id or "",
            "workflow_id": workflow_id,
            "request_status": updated.get("status"),
            "routed_at": _utc_now(),
            "source": "simulated_hr_services_store",
            "idempotent_replay": False,
        }
        self._routes[key] = record
        return copy.deepcopy(record)

    def evaluate_authorization(
        self,
        *,
        category: str,
        target_employee_id: str,
        requester_user_id: str = "",
        requester_role: str = "",
        organization_id: str = "",
        candidate_id: str = "",
    ) -> dict[str, Any]:
        """Deterministic authorization suitable for current architecture."""

        self._maybe_fault("evaluate_authorization")
        policy = self.get_policy(organization_id=organization_id)
        privileged = {
            str(item).lower() for item in (policy.get("privileged_roles") or [])
        }
        recruitment_roles = {
            str(item).lower() for item in (policy.get("recruitment_roles") or [])
        }
        sensitive = set(policy.get("sensitive_categories") or [])
        role = (requester_role or "").strip().lower()
        requester = (requester_user_id or "").strip().upper()
        target = _employee_key(target_employee_id) if target_employee_id else ""

        allowed = True
        reason = "Authorized."
        disclosure_blocked = False

        # No identity context → demo/CLI mode allows non-recruitment reads.
        if not requester and not role:
            if category == "recruitment_status" and candidate_id:
                allowed = True
                reason = "Demo mode allows recruitment status lookup."
            else:
                allowed = True
                reason = "No requester identity provided; demo mode allows service handling."
            return {
                "allowed": allowed,
                "reason": reason,
                "disclosure_blocked": False,
                "self_service": bool(target and requester and requester == target),
                "role": role or None,
                "organization_id": organization_id or None,
            }

        is_self = bool(target and requester and requester == target)
        is_privileged = role in privileged

        if category in sensitive and target and not is_self and not is_privileged:
            allowed = False
            disclosure_blocked = True
            reason = (
                f"Requester {requester or 'unknown'} is not authorized to access "
                f"{category} data for employee {target}."
            )
        elif category == "recruitment_status" and role and role not in recruitment_roles:
            allowed = False
            disclosure_blocked = True
            reason = "Recruitment status requires HR/recruiter authority."
        elif category == "payroll_routing" and not is_self and not is_privileged:
            allowed = False
            disclosure_blocked = True
            reason = "Payroll issues for another employee require HR/manager authority."

        return {
            "allowed": allowed,
            "reason": reason,
            "disclosure_blocked": disclosure_blocked,
            "self_service": is_self,
            "role": role or None,
            "organization_id": organization_id or None,
        }

    def validate_service_policy(
        self,
        *,
        category: str,
        employee: dict[str, Any] | None = None,
        authorization: dict[str, Any] | None = None,
        service_data: dict[str, Any] | None = None,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("validate_service_policy")
        policy = self.get_policy(organization_id=organization_id)
        auth = dict(authorization or {})
        data = dict(service_data or {})
        emp = dict(employee or {})
        violations: list[str] = []
        warnings: list[str] = []
        requires_human_approval = False
        approval_level = None
        severity = "ready"
        eligible_for_action = True
        route_hint = "resolve"

        if not auth.get("allowed", True):
            violations.append(str(auth.get("reason") or "Authorization failed."))
            severity = "blocked"
            eligible_for_action = False
            route_hint = "escalate"

        if category in (policy.get("approval_categories") or []):
            requires_human_approval = True
            approval_level = "hr"
            severity = "pending_approval"
            eligible_for_action = False
            route_hint = "escalate"

        if category in (policy.get("escalation_categories") or []):
            # Ticket creation is the escalation mechanism; no approval pause required.
            severity = "escalate"
            requires_human_approval = False
            approval_level = "hr_payroll"
            eligible_for_action = True
            route_hint = "create_ticket"

        if category in (policy.get("document_categories") or []):
            route_hint = "create_ticket"
            severity = "ready"
            eligible_for_action = True

        if category in (policy.get("ticket_categories") or []) and category not in (
            policy.get("approval_categories") or []
        ) and category not in (policy.get("escalation_categories") or []):
            route_hint = "create_ticket"
            severity = "ready"
            eligible_for_action = True

        if category in (policy.get("auto_resolvable_categories") or []):
            if severity not in {"blocked", "pending_approval", "escalate"}:
                route_hint = "resolve"
                severity = "ready"
                eligible_for_action = True

        if category == "recruitment_status" and not data.get("candidate"):
            if not violations:
                warnings.append("Candidate record was not retrieved.")
                if severity == "ready":
                    severity = "recommend"
                    eligible_for_action = False
                    route_hint = "escalate"

        if category in {"leave_balance", "attendance", "onboarding"}:
            if not emp.get("employee_id") and not data.get("employee_id"):
                violations.append("Employee context is required for this HR service.")
                severity = "blocked"
                eligible_for_action = False
                route_hint = "escalate"

        if category == "employment_document":
            if not emp.get("employee_id") and not data.get("employee_id"):
                violations.append("Employee context is required for document requests.")
                severity = "blocked"
                eligible_for_action = False
                route_hint = "escalate"

        if category == "leave_balance" and data.get("leave_balance") is None and not violations:
            if data.get("leave_balance_error"):
                violations.append(str(data.get("leave_balance_error")))
                severity = "blocked"
                eligible_for_action = False

        return {
            "policy_id": policy.get("policy_id"),
            "severity": severity,
            "outcome_hint": severity,
            "eligible_for_action": eligible_for_action,
            "requires_human_approval": requires_human_approval,
            "approval_level": approval_level,
            "route_hint": route_hint,
            "violations": violations,
            "warnings": warnings,
            "exceptions": list(policy.get("forbidden_auto_changes") or []),
            "category": category,
            "authorization": auth,
        }


_STORE: SimulatedHRServicesStore | None = None


def get_hr_services_store() -> SimulatedHRServicesStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedHRServicesStore()
    return _STORE


def reset_hr_services_store() -> SimulatedHRServicesStore:
    store = get_hr_services_store()
    store.reset()
    return store
