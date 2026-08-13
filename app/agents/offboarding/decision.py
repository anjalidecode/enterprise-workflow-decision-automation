"""Offboarding Decision Agent: produce WorkflowDecision for offboarding."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, recall_long_term, search_short_term
from app.models.decision import WorkflowDecision
from app.orchestration.state import WorkflowState


def build_offboarding_pending_actions(
    *,
    employee_id: str,
    manager_id: str | None,
    analysis: dict[str, Any],
    rationale: str,
    include_privileged: bool,
    include_standard_access_revoke: bool = True,
) -> list[dict[str, Any]]:
    if not employee_id:
        return []

    actions: list[dict[str, Any]] = []
    for task_type in analysis.get("mandatory_tasks") or ["manager_review", "hr_review"]:
        actions.append(
            {
                "type": "create_offboarding_task",
                "employee_id": employee_id,
                "task_type": task_type,
                "details": f"Exit checklist item: {task_type}",
            }
        )

    for asset in analysis.get("outstanding_assets") or []:
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id:
            continue
        actions.append(
            {
                "type": "request_asset_return",
                "employee_id": employee_id,
                "asset_id": asset_id,
            }
        )

    handover = dict(analysis.get("handover") or {})
    if analysis.get("exit_record", {}).get("handover_required") or handover.get("required"):
        actions.append(
            {
                "type": "create_offboarding_handover",
                "employee_id": employee_id,
                "projects": list(handover.get("projects") or []),
                "documents": list(handover.get("documents") or []),
                "knowledge_areas": list(handover.get("knowledge_areas") or []),
                "manager": str(manager_id or handover.get("manager") or ""),
            }
        )

    if analysis.get("exit_record", {}).get("exit_interview_required", True):
        actions.append(
            {
                "type": "schedule_exit_interview",
                "employee_id": employee_id,
                "scheduled_for": str(analysis.get("last_working_day") or "TBD"),
            }
        )

    standard_systems = [
        system
        for system in (analysis.get("access_systems") or [])
        if system not in set(analysis.get("privileged_systems") or [])
    ]
    if include_standard_access_revoke and standard_systems:
        actions.append(
            {
                "type": "create_access_revoke_request",
                "employee_id": employee_id,
                "systems": standard_systems,
                "privileged": False,
            }
        )

    if include_privileged:
        privileged_systems = list(analysis.get("privileged_systems") or [])
        if privileged_systems:
            actions.append(
                {
                    "type": "create_access_revoke_request",
                    "employee_id": employee_id,
                    "systems": privileged_systems,
                    "privileged": True,
                }
            )

    actions.append(
        {
            "type": "update_offboarding_status",
            "employee_id": employee_id,
            "status": "preparation_in_progress" if not include_privileged else "approved_preparation",
        }
    )
    actions.append(
        {
            "type": "notify_employee",
            "employee_id": employee_id,
            "message": (
                f"Offboarding preparation started for employee {employee_id}. {rationale}"
            ),
        }
    )
    if manager_id:
        actions.append(
            {
                "type": "notify_employee",
                "employee_id": manager_id,
                "message": (
                    f"Offboarding preparation for employee {employee_id} requires your review. "
                    f"{rationale}"
                ),
            }
        )
    return actions


def offboarding_decision_agent(state: WorkflowState) -> dict[str, Any]:
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    employee = state.get("employee_data") or {}
    employee_id = str(
        analysis.get("employee_id")
        or employee.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    manager_id = str(employee.get("manager") or analysis.get("manager") or "") or None
    patches: list[dict[str, Any]] = []

    _, notes_patch = search_short_term(state, agent="offboarding_decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(
        state,
        agent="offboarding_decision",
        employee_id=employee_id or None,
        workflow_type="offboarding",
    )
    patches.append(history_patch)

    blockers = list(analysis.get("blockers") or policy.get("violations") or [])
    warnings = list(analysis.get("warnings") or policy.get("warnings") or [])
    evidence = [
        f"severity={policy.get('severity')}",
        f"exit_type={analysis.get('exit_type')}",
        f"last_working_day={analysis.get('last_working_day')}",
        f"outstanding_assets={len(analysis.get('outstanding_assets') or [])}",
        f"privileged={analysis.get('privileged_access')}",
        f"pending_tasks={analysis.get('pending_tasks') or []}",
    ]
    if history:
        warnings.append("Prior offboarding outcomes were available as context only.")

    pending_actions: list[dict[str, Any]] = []
    severity = str(policy.get("severity") or analysis.get("recommendation") or "blocked")

    if severity == "blocked" or blockers or not employee_id:
        outcome = "blocked"
        executable = False
        requires_human_approval = False
        confidence = 0.95
        rationale = (
            "Offboarding is blocked due to missing mandatory information, notice-period "
            "issues, or policy violations: "
            + ("; ".join(str(item) for item in blockers) if blockers else "insufficient data.")
        )
    elif severity == "pending_approval" or policy.get("requires_human_approval"):
        outcome = "pending_approval"
        executable = False
        requires_human_approval = True
        confidence = 0.9
        rationale = (
            f"Offboarding for {employee_id} requires human approval before privileged "
            f"access-revocation request/finalization "
            f"(approval_level={policy.get('approval_level') or 'hr_manager'}). "
            "No privileged write actions have been executed."
        )
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = [
            {
                "type": "request_human_approval",
                "employee_id": employee_id,
                "approval_level": policy.get("approval_level"),
                "reason": "privileged_access",
            }
        ]
    elif severity == "ready":
        outcome = "ready"
        executable = True
        requires_human_approval = False
        confidence = 0.9
        rationale = (
            f"Offboarding preparation is ready for {employee_id}: "
            f"exit_type={analysis.get('exit_type')}, "
            f"last_working_day={analysis.get('last_working_day')}, "
            f"outstanding_assets={len(analysis.get('outstanding_assets') or [])}. "
            "Checklist, asset-return, handover, and exit-interview coordination can proceed. "
            "Employment status will not be changed automatically."
        )
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = build_offboarding_pending_actions(
            employee_id=employee_id,
            manager_id=manager_id,
            analysis=analysis,
            rationale=rationale,
            include_privileged=False,
            include_standard_access_revoke=True,
        )
    else:
        outcome = "recommend"
        executable = False
        requires_human_approval = False
        confidence = 0.84
        rationale = (
            f"Offboarding recommendations prepared for {employee_id}. "
            "No automated write actions scheduled."
        )

    decision = WorkflowDecision(
        outcome=outcome,  # type: ignore[arg-type]
        rationale=rationale,
        executable=executable,
        confidence=confidence,
        requires_human_approval=requires_human_approval,
        entity_refs={
            "employee_id": employee_id or None,
            "manager_id": manager_id,
            "department": employee.get("department") or analysis.get("department"),
            "exit_type": analysis.get("exit_type"),
            "last_working_day": analysis.get("last_working_day"),
            "privileged_access": analysis.get("privileged_access"),
            "approval_level": policy.get("approval_level"),
            "severity": severity,
        },
        evidence=evidence,
        blockers=blockers,
        warnings=warnings,
        influenced_by=[item.memory_id for item in history],
    )

    metadata = dict(state.get("metadata") or {})
    metadata["offboarding_severity"] = severity
    metadata["offboarding_recommendation"] = outcome
    metadata["privileged_access"] = bool(analysis.get("privileged_access"))

    _, memory_patch = append_short_term(
        state,
        agent="offboarding_decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; executable={decision.executable}; "
            f"approval={decision.requires_human_approval}; "
            f"privileged={analysis.get('privileged_access')}."
        ),
        influenced_decision=bool(history or warnings),
    )
    patches.append(memory_patch)

    return node_update(
        "offboarding_decision",
        f"Decision={decision.outcome}; employee={employee_id}; executable={decision.executable}.",
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        metadata=metadata,
        **combine_patches(*patches),
    )
