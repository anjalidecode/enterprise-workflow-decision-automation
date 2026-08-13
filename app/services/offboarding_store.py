"""In-memory offboarding store: exits, assets, handover, policy, tasks.

JSON seeds are loaded once per reset and never written back.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError
from app.services.offboarding_data import (
    load_exit_records,
    load_offboarding_assets,
    load_offboarding_handover,
    load_offboarding_policy,
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


def _parse_date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return None


class SimulatedOffboardingStore:
    """Mutable offboarding exit/checklist/asset/handover writes for workflow runs."""

    def __init__(self) -> None:
        self._exits: list[dict[str, Any]] = []
        self._assets: list[dict[str, Any]] = []
        self._handovers: list[dict[str, Any]] = []
        self._policy: dict[str, Any] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._asset_returns: dict[str, dict[str, Any]] = {}
        self._handover_tasks: dict[str, dict[str, Any]] = {}
        self._exit_interviews: dict[str, dict[str, Any]] = {}
        self._access_requests: dict[str, dict[str, Any]] = {}
        self._statuses: dict[str, dict[str, Any]] = {}
        self._checklists: dict[str, dict[str, Any]] = {}
        self._faults: dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        self._exits = [copy.deepcopy(item) for item in load_exit_records()]
        self._assets = [copy.deepcopy(item) for item in load_offboarding_assets()]
        self._handovers = [copy.deepcopy(item) for item in load_offboarding_handover()]
        self._policy = copy.deepcopy(load_offboarding_policy())
        self._tasks = {}
        self._asset_returns = {}
        self._handover_tasks = {}
        self._exit_interviews = {}
        self._access_requests = {}
        self._statuses = {}
        self._checklists = {}
        self._faults = {}

    def inject_error(self, operation: str, times: int = 1) -> None:
        self._faults[operation] = times

    def _maybe_fault(self, operation: str) -> None:
        remaining = self._faults.get(operation, 0)
        if remaining > 0:
            self._faults[operation] = remaining - 1
            raise SimulatedServiceError(f"Simulated offboarding error during {operation}.")

    def get_exit(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any] | None:
        self._maybe_fault("get_exit")
        key = _employee_key(employee_id)
        for item in self._exits:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            # Prefer exact org match when organization_id is provided.
            if organization_id and str(item.get("organization_id") or "") == organization_id:
                return copy.deepcopy(item)
        for item in self._exits:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if not organization_id and str(item.get("organization_id") or ""):
                continue
            return copy.deepcopy(item)
        return None

    def list_assets(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        self._maybe_fault("list_assets")
        key = _employee_key(employee_id)
        results: list[dict[str, Any]] = []
        for item in self._assets:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if organization_id:
                if str(item.get("organization_id") or "") not in {"", organization_id}:
                    continue
            elif str(item.get("organization_id") or ""):
                continue
            results.append(copy.deepcopy(item))
        results.sort(key=lambda row: str(row.get("asset_id") or ""))
        return results

    def get_handover(
        self,
        employee_id: str,
        *,
        organization_id: str = "",
    ) -> dict[str, Any] | None:
        self._maybe_fault("get_handover")
        key = _employee_key(employee_id)
        for item in self._handovers:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if organization_id and str(item.get("organization_id") or "") == organization_id:
                return copy.deepcopy(item)
        for item in self._handovers:
            if _employee_key(str(item.get("employee_id") or "")) != key:
                continue
            if not _org_matches(item, organization_id):
                continue
            if not organization_id and str(item.get("organization_id") or ""):
                continue
            return copy.deepcopy(item)
        return None

    def get_policy(self, *, organization_id: str = "") -> dict[str, Any]:
        self._maybe_fault("get_policy")
        policy = copy.deepcopy(self._policy)
        if organization_id:
            policy["organization_id"] = organization_id
        return policy

    def build_checklist(
        self,
        *,
        employee_id: str,
        exit_record: dict[str, Any] | None = None,
        assets: list[dict[str, Any]] | None = None,
        handover: dict[str, Any] | None = None,
        policy: dict[str, Any] | None = None,
        organization_id: str = "",
        workflow_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("build_checklist")
        key = _employee_key(employee_id)
        exit_doc = exit_record or self.get_exit(key, organization_id=organization_id) or {}
        asset_rows = assets if assets is not None else self.list_assets(key, organization_id=organization_id)
        handover_doc = (
            handover
            if handover is not None
            else self.get_handover(key, organization_id=organization_id) or {}
        )
        policy_doc = policy or self.get_policy(organization_id=organization_id)
        mandatory = list(policy_doc.get("mandatory_checklist_items") or [])

        completed_task_types = {
            str(item.get("task_type") or "")
            for item in self._tasks.values()
            if _employee_key(str(item.get("employee_id") or "")) == key
            and (not organization_id or _org_matches(item, organization_id))
        }
        if any(
            _employee_key(str(item.get("employee_id") or "")) == key
            and (not organization_id or _org_matches(item, organization_id))
            for item in self._asset_returns.values()
        ):
            completed_task_types.add("asset_return")
        if any(
            _employee_key(str(item.get("employee_id") or "")) == key
            and (not organization_id or _org_matches(item, organization_id))
            for item in self._handover_tasks.values()
        ):
            completed_task_types.add("knowledge_handover")
        if any(
            _employee_key(str(item.get("employee_id") or "")) == key
            and (not organization_id or _org_matches(item, organization_id))
            for item in self._exit_interviews.values()
        ):
            completed_task_types.add("exit_interview")
        if any(
            _employee_key(str(item.get("employee_id") or "")) == key
            and (not organization_id or _org_matches(item, organization_id))
            for item in self._access_requests.values()
        ):
            completed_task_types.add("access_revocation_request")

        outstanding_assets = [
            item
            for item in asset_rows
            if str(item.get("return_status") or "").lower() in {"", "outstanding", "assigned"}
        ]
        items: list[dict[str, Any]] = []
        blockers: list[str] = []
        pending: list[str] = []
        completed: list[str] = []
        dependencies: dict[str, list[str]] = {
            "access_revocation_request": ["manager_review", "hr_review"],
            "exit_interview": ["manager_review"],
        }

        for task_type in mandatory:
            status = "completed" if task_type in completed_task_types else "pending"
            if task_type == "asset_return" and outstanding_assets and status != "completed":
                status = "pending"
            if task_type == "knowledge_handover":
                handover_status = str(handover_doc.get("handover_status") or "not_started")
                if handover_status == "completed" or task_type in completed_task_types:
                    status = "completed"
                else:
                    status = "pending"
            item = {
                "task_type": task_type,
                "status": status,
                "required": True,
                "dependencies": list(dependencies.get(task_type) or []),
            }
            items.append(item)
            if status == "completed":
                completed.append(task_type)
            else:
                pending.append(task_type)

        if not exit_doc:
            blockers.append("Exit record is missing.")
        if exit_doc.get("mandatory_fields_complete") is False:
            missing = list(exit_doc.get("missing_mandatory_fields") or [])
            blockers.append(
                "Mandatory exit information is incomplete"
                + (f": {', '.join(missing)}" if missing else ".")
            )

        checklist = {
            "employee_id": key,
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "items": items,
            "completed_tasks": completed,
            "pending_tasks": pending,
            "blockers": blockers,
            "dependencies": dependencies,
            "outstanding_asset_ids": [str(item.get("asset_id")) for item in outstanding_assets],
            "handover_status": handover_doc.get("handover_status"),
            "source": "simulated_offboarding_store",
        }
        cache_key = f"{workflow_id}:{key}:{organization_id}"
        self._checklists[cache_key] = copy.deepcopy(checklist)
        return copy.deepcopy(checklist)

    def validate_offboarding_policy(
        self,
        *,
        employee: dict[str, Any],
        exit_record: dict[str, Any] | None = None,
        checklist: dict[str, Any] | None = None,
        assets: list[dict[str, Any]] | None = None,
        handover: dict[str, Any] | None = None,
        policy: dict[str, Any] | None = None,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("validate_offboarding_policy")
        policy_doc = policy or self.get_policy(organization_id=organization_id)
        thresholds = dict(policy_doc.get("thresholds") or {})
        rules = dict(policy_doc.get("rules") or {})
        outcomes = dict(policy_doc.get("outcomes") or {})
        mandatory_fields = list(policy_doc.get("mandatory_exit_fields") or [])

        employee_id = str(employee.get("employee_id") or "")
        exit_doc = exit_record or self.get_exit(employee_id, organization_id=organization_id) or {}
        asset_rows = (
            assets
            if assets is not None
            else self.list_assets(employee_id, organization_id=organization_id)
        )
        handover_doc = (
            handover
            if handover is not None
            else self.get_handover(employee_id, organization_id=organization_id) or {}
        )
        checklist_doc = checklist or {}

        violations: list[str] = []
        warnings: list[str] = []
        exceptions: list[str] = []
        requires_human_approval = False
        approval_level = None
        severity = "ready"
        outcome_hint = outcomes.get("ready", "ready")

        if rules.get("employee_must_be_active") and employee.get("employment_status") != "active":
            violations.append("Employee must be active for offboarding preparation.")
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")

        if not exit_doc:
            violations.append("Exit/resignation record is required.")
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")

        if rules.get("mandatory_exit_fields_required"):
            missing_fields: list[str] = []
            if exit_doc.get("mandatory_fields_complete") is False:
                missing_fields = list(exit_doc.get("missing_mandatory_fields") or [])
            for field in mandatory_fields:
                value = exit_doc.get(field)
                if value in (None, "", []):
                    if field not in missing_fields:
                        missing_fields.append(field)
            if missing_fields:
                violations.append(
                    "Missing mandatory exit information: " + ", ".join(missing_fields) + "."
                )
                severity = "blocked"
                outcome_hint = outcomes.get("blocked", "blocked")

        if rules.get("enforce_notice_period") and severity != "blocked" and exit_doc:
            min_notice = int(
                thresholds.get("minimum_notice_period_days")
                or exit_doc.get("notice_period_days")
                or employee.get("notice_period_days")
                or 30
            )
            resignation = _parse_date(exit_doc.get("resignation_date"))
            last_day = _parse_date(exit_doc.get("requested_last_working_day"))
            if resignation and last_day:
                provided = (last_day - resignation).days
                if provided < min_notice:
                    violations.append(
                        f"Notice period {provided} days is below required {min_notice} days."
                    )
                    severity = "blocked"
                    outcome_hint = outcomes.get("blocked", "blocked")
            elif exit_doc.get("resignation_date") or exit_doc.get("requested_last_working_day"):
                # Partial dates already covered by mandatory fields; keep deterministic.
                pass

        outstanding_assets = [
            item
            for item in asset_rows
            if str(item.get("return_status") or "").lower() in {"", "outstanding", "assigned"}
        ]
        if rules.get("outstanding_assets_are_warnings") and outstanding_assets and severity != "blocked":
            warnings.append(
                f"{len(outstanding_assets)} asset(s) outstanding and require return tasks."
            )

        handover_required = bool(
            exit_doc.get("handover_required")
            or handover_doc.get("required")
            or rules.get("knowledge_handover_required")
        )
        handover_incomplete = str(handover_doc.get("handover_status") or "not_started") != "completed"
        if (
            rules.get("incomplete_handover_is_warning")
            and handover_required
            and handover_incomplete
            and severity != "blocked"
        ):
            warnings.append("Mandatory knowledge handover is incomplete.")

        privileged = bool(exit_doc.get("privileged_access")) or bool(exit_doc.get("privileged_systems"))
        if (
            rules.get("privileged_access_requires_human_approval")
            and privileged
            and severity != "blocked"
        ):
            requires_human_approval = True
            approval_level = "hr_manager"
            severity = "pending_approval"
            outcome_hint = outcomes.get("pending_approval", "pending_approval")
            warnings.append(
                "Privileged system access detected; human approval required before "
                "access-revocation request/finalization."
            )

        if rules.get("employment_status_change_requires_human_approval"):
            exceptions.append("Employment-status changes require human approval and are not automated.")
        if rules.get("no_automatic_termination"):
            exceptions.append("Automatic employment termination is not permitted.")
        if rules.get("no_automatic_privileged_access_revocation"):
            exceptions.append("Automatic privileged-access revocation is not permitted.")
        if rules.get("access_revocation_is_request_only"):
            exceptions.append("Access revocation creates requests only; it does not revoke privileges directly.")

        if checklist_doc.get("blockers") and severity != "blocked":
            for blocker in checklist_doc.get("blockers") or []:
                if blocker not in violations:
                    violations.append(str(blocker))
            severity = "blocked"
            outcome_hint = outcomes.get("blocked", "blocked")
            requires_human_approval = False

        if rules.get("manager_approval_required") and severity == "ready":
            warnings.append("Manager review is required as part of the exit checklist.")
        if rules.get("hr_approval_required") and severity == "ready":
            warnings.append("HR review is required as part of the exit checklist.")

        eligible_for_action = severity == "ready" and not requires_human_approval and not violations
        return {
            "policy_id": policy_doc.get("policy_id"),
            "severity": severity,
            "outcome_hint": outcome_hint,
            "eligible_for_action": eligible_for_action,
            "requires_human_approval": requires_human_approval,
            "approval_level": approval_level,
            "violations": violations,
            "warnings": warnings,
            "exceptions": exceptions,
            "privileged_access": privileged,
            "outstanding_asset_count": len(outstanding_assets),
            "handover_required": handover_required,
            "thresholds_applied": {
                "minimum_notice_period_days": int(thresholds.get("minimum_notice_period_days") or 30),
            },
            "source": "simulated_offboarding_store",
        }

    def create_task(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        task_type: str,
        details: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_task")
        key = build_idempotency_key(
            capability="offboarding.task.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=str(task_type),
        )
        existing = self._tasks.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        record = {
            "task_id": f"OT-{_employee_key(employee_id)}-{task_type}-{len(self._tasks) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "task_type": task_type,
            "details": details,
            "status": "created",
            "created_at": _utc_now(),
            "source": "simulated_offboarding_store",
            "idempotent_replay": False,
        }
        self._tasks[key] = record
        return copy.deepcopy(record)

    def request_asset_return(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        asset_id: str,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("request_asset_return")
        key = build_idempotency_key(
            capability="offboarding.asset.return",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=str(asset_id).upper(),
        )
        existing = self._asset_returns.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        matched = None
        for item in self._assets:
            if str(item.get("asset_id") or "").upper() != str(asset_id).upper():
                continue
            if _employee_key(str(item.get("employee_id") or "")) != _employee_key(employee_id):
                continue
            matched = item
            item["return_status"] = "return_requested"
            break
        if matched is None:
            raise SimulatedServiceError(f"Asset {asset_id} not found for employee {employee_id}.")
        record = {
            "return_id": f"AR-{str(asset_id).upper()}",
            "asset_id": str(asset_id).upper(),
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "asset_type": matched.get("asset_type"),
            "status": "return_requested",
            "created_at": _utc_now(),
            "source": "simulated_offboarding_store",
            "idempotent_replay": False,
        }
        self._asset_returns[key] = record
        return copy.deepcopy(record)

    def create_handover(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        projects: list[str] | None = None,
        documents: list[str] | None = None,
        knowledge_areas: list[str] | None = None,
        manager: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_handover")
        key = build_idempotency_key(
            capability="offboarding.handover.create",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel="handover",
        )
        existing = self._handover_tasks.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        seed = self.get_handover(employee_id, organization_id=organization_id) or {}
        record = {
            "handover_task_id": f"HT-{_employee_key(employee_id)}-{len(self._handover_tasks) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "manager": manager or seed.get("manager"),
            "projects": list(projects if projects is not None else seed.get("projects") or []),
            "documents": list(documents if documents is not None else seed.get("documents") or []),
            "knowledge_areas": list(
                knowledge_areas if knowledge_areas is not None else seed.get("knowledge_areas") or []
            ),
            "status": "handover_task_created",
            "created_at": _utc_now(),
            "source": "simulated_offboarding_store",
            "idempotent_replay": False,
        }
        self._handover_tasks[key] = record
        for item in self._handovers:
            if _employee_key(str(item.get("employee_id") or "")) != _employee_key(employee_id):
                continue
            if not _org_matches(item, organization_id):
                continue
            item["handover_status"] = "in_progress"
            break
        return copy.deepcopy(record)

    def schedule_exit_interview(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        scheduled_for: str = "",
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("schedule_exit_interview")
        key = build_idempotency_key(
            capability="offboarding.exit_interview.schedule",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=scheduled_for or "default",
        )
        existing = self._exit_interviews.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        record = {
            "interview_id": f"EI-{_employee_key(employee_id)}-{len(self._exit_interviews) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "scheduled_for": scheduled_for or "TBD",
            "status": "scheduled",
            "created_at": _utc_now(),
            "source": "simulated_offboarding_store",
            "idempotent_replay": False,
        }
        self._exit_interviews[key] = record
        return copy.deepcopy(record)

    def create_access_revoke_request(
        self,
        *,
        workflow_id: str,
        employee_id: str,
        systems: list[str] | None = None,
        privileged: bool = False,
        organization_id: str = "",
    ) -> dict[str, Any]:
        self._maybe_fault("create_access_revoke_request")
        system_key = ",".join(sorted(str(item) for item in (systems or [])))
        key = build_idempotency_key(
            capability="offboarding.access.revoke_request",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=f"{'priv' if privileged else 'std'}:{system_key}",
        )
        existing = self._access_requests.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        record = {
            "request_id": f"AXR-{_employee_key(employee_id)}-{len(self._access_requests) + 1}",
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "systems": list(systems or []),
            "privileged": bool(privileged),
            "status": "revocation_requested",
            "created_at": _utc_now(),
            "note": "Request only; privileges are not revoked automatically.",
            "source": "simulated_offboarding_store",
            "idempotent_replay": False,
        }
        self._access_requests[key] = record
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
            capability="offboarding.status.update",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=_employee_key(employee_id),
            channel=str(status),
        )
        existing = self._statuses.get(key)
        if existing is not None:
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        record = {
            "employee_id": _employee_key(employee_id),
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "status": status,
            "updated_at": _utc_now(),
            "source": "simulated_offboarding_store",
            "idempotent_replay": False,
        }
        self._statuses[key] = record
        return copy.deepcopy(record)

    def list_tasks(
        self,
        *,
        employee_id: str = "",
        workflow_id: str = "",
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in self._tasks.values():
            if employee_id and _employee_key(str(item.get("employee_id") or "")) != _employee_key(
                employee_id
            ):
                continue
            if workflow_id and item.get("workflow_id") != workflow_id:
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        return results

    def list_access_requests(
        self,
        *,
        employee_id: str = "",
        workflow_id: str = "",
        organization_id: str = "",
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in self._access_requests.values():
            if employee_id and _employee_key(str(item.get("employee_id") or "")) != _employee_key(
                employee_id
            ):
                continue
            if workflow_id and item.get("workflow_id") != workflow_id:
                continue
            if not _org_matches(item, organization_id):
                continue
            results.append(copy.deepcopy(item))
        return results


_STORE: SimulatedOffboardingStore | None = None


def get_offboarding_store() -> SimulatedOffboardingStore:
    global _STORE
    if _STORE is None:
        _STORE = SimulatedOffboardingStore()
    return _STORE


def reset_offboarding_store() -> SimulatedOffboardingStore:
    global _STORE
    _STORE = SimulatedOffboardingStore()
    return _STORE
