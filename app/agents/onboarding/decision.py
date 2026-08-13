"""Onboarding Decision Agent: produce WorkflowDecision for onboarding."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, recall_long_term, search_short_term
from app.models.decision import WorkflowDecision
from app.orchestration.state import WorkflowState


def build_onboarding_pending_actions(
    *,
    employee_id: str,
    analysis: dict[str, Any],
    include_privileged: bool,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for task_type in analysis.get("mandatory_tasks") or []:
        actions.append(
            {
                "type": "create_onboarding_task",
                "employee_id": employee_id,
                "task_type": task_type,
            }
        )
    for item in analysis.get("equipment_required") or []:
        actions.append(
            {
                "type": "request_equipment",
                "employee_id": employee_id,
                "item": item,
            }
        )
    for system in analysis.get("access_required") or []:
        actions.append(
            {
                "type": "request_system_access",
                "employee_id": employee_id,
                "system": system,
                "privileged": False,
            }
        )
    if include_privileged:
        for system in analysis.get("privileged_access_required") or []:
            actions.append(
                {
                    "type": "request_system_access",
                    "employee_id": employee_id,
                    "system": system,
                    "privileged": True,
                }
            )
    actions.append(
        {
            "type": "update_onboarding_status",
            "employee_id": employee_id,
            "status": "in_progress",
        }
    )
    actions.append(
        {
            "type": "notify_employee",
            "employee_id": employee_id,
            "message": f"Onboarding actions started for employee {employee_id}.",
        }
    )
    return actions


def onboarding_decision_agent(state: WorkflowState) -> dict[str, Any]:
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    employee = state.get("employee_data") or {}
    employee_id = str(
        analysis.get("employee_id")
        or employee.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    patches: list[dict[str, Any]] = []

    _, notes_patch = search_short_term(state, agent="onboarding_decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(
        state,
        agent="onboarding_decision",
        employee_id=employee_id or None,
    )
    patches.append(history_patch)

    blockers = list(analysis.get("blockers") or policy.get("violations") or [])
    warnings = list(analysis.get("warnings") or policy.get("warnings") or [])
    recommendation = analysis.get("recommendation") or "blocked"
    evidence = [
        f"policy_eligible={policy.get('eligible')}",
        f"documents_verified={analysis.get('verified_documents') or []}",
        f"missing={analysis.get('missing_documents') or []}",
        f"privileged={analysis.get('privileged_access_required') or []}",
    ]

    if history:
        warnings.append("Prior onboarding outcomes were available as context only.")

    pending_actions: list[dict[str, Any]] = []
    if recommendation == "blocked" or blockers or not policy.get("eligible"):
        outcome = "blocked"
        executable = False
        requires_human_approval = False
        confidence = 0.95
        rationale = (
            "Onboarding is blocked due to policy or document issues: "
            + ("; ".join(blockers) if blockers else "eligibility failed.")
        )
    elif recommendation == "pending_approval" or policy.get("requires_human_approval"):
        outcome = "pending_approval"
        executable = False
        requires_human_approval = True
        confidence = 0.88
        privileged = analysis.get("privileged_access_required") or []
        rationale = (
            "Onboarding requires human approval before privileged access provisioning: "
            + ", ".join(str(item) for item in privileged)
            + "."
        )
        pending_actions = [
            {
                "type": "request_human_approval",
                "employee_id": employee_id,
                "privileged_access": privileged,
            }
        ]
    else:
        outcome = "ready"
        executable = True
        requires_human_approval = False
        confidence = 0.9 if not warnings else 0.82
        rationale = (
            f"Employee {employee_id} is ready for onboarding task creation, "
            "equipment requests, and standard system access."
        )
        pending_actions = build_onboarding_pending_actions(
            employee_id=employee_id,
            analysis=analysis,
            include_privileged=False,
        )

    decision = WorkflowDecision(
        outcome=outcome,  # type: ignore[arg-type]
        rationale=rationale,
        executable=executable,
        confidence=confidence,
        requires_human_approval=requires_human_approval,
        entity_refs={
            "employee_id": employee_id,
            "role": employee.get("role") or analysis.get("role"),
            "department": employee.get("department") or analysis.get("department"),
        },
        evidence=evidence,
        blockers=blockers,
        warnings=warnings,
        influenced_by=[item.memory_id for item in history],
    )

    metadata = dict(state.get("metadata") or {})
    metadata["onboarding_recommendation"] = recommendation

    _, memory_patch = append_short_term(
        state,
        agent="onboarding_decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; executable={decision.executable}; "
            f"approval={decision.requires_human_approval}."
        ),
        influenced_decision=bool(history or warnings),
    )
    patches.append(memory_patch)

    return node_update(
        "onboarding_decision",
        f"Decision={decision.outcome}; executable={decision.executable}.",
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        metadata=metadata,
        **combine_patches(*patches),
    )
