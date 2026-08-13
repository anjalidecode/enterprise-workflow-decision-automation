"""Onboarding Response Agent: summarize outcomes and persist compact LTM."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState


def onboarding_response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    completed = list(state.get("completed_actions") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="onboarding_response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="onboarding_response",
        query="onboarding process document verification approval procedures",
        workflow_type="onboarding",
    )
    patches.append(knowledge_patch)

    status = state.get("status") or "completed"
    if status == "awaiting_human_approval":
        final_status = "awaiting_human_approval"
    elif status == "validation_failed":
        final_status = "validation_failed"
    else:
        final_status = "completed"

    handbook = hits[0].title if hits else "Onboarding handbook"
    employee_label = (
        f"{employee.get('name') or 'Unknown'} "
        f"({employee.get('employee_id') or analysis.get('employee_id') or 'n/a'})"
    )
    outcome = decision.get("outcome")
    missing = analysis.get("missing_documents") or []
    invalid = analysis.get("invalid_documents") or []
    blockers = decision.get("blockers") or analysis.get("blockers") or []
    warnings = decision.get("warnings") or analysis.get("warnings") or []

    tasks_created = [item for item in completed if item.get("type") == "create_onboarding_task"]
    equipment = [item for item in completed if item.get("type") == "request_equipment"]
    access = [item for item in completed if item.get("type") == "request_system_access"]
    notifications = [item for item in completed if item.get("type") == "notify_employee"]

    if final_status == "awaiting_human_approval":
        response = (
            f"Onboarding for {employee_label} requires human approval before write actions. "
            f"Privileged access: {', '.join(analysis.get('privileged_access_required') or []) or 'none'}. "
            f"Reason: {decision.get('rationale')}. "
            f"Missing docs: {', '.join(missing) or 'none'}. Handbook: {handbook}."
        )
    elif outcome == "blocked":
        response = (
            f"Onboarding for {employee_label} is blocked. "
            f"Missing documents: {', '.join(missing) or 'none'}. "
            f"Invalid documents: {', '.join(invalid) or 'none'}. "
            f"Blockers: {'; '.join(str(item) for item in blockers) or 'none'}. "
            f"No write actions were executed. Handbook: {handbook}."
        )
    else:
        response = (
            f"Onboarding actions completed for {employee_label}. "
            f"Tasks created via tools: {len(tasks_created)}; "
            f"equipment requests via tools: {len(equipment)}; "
            f"access requests via tools: {len(access)}; "
            f"notifications via tools: {len(notifications)}. "
            f"Warnings: {'; '.join(str(item) for item in warnings) or 'none'}. "
            f"Handbook: {handbook}."
        )

    try:
        _, ltm_patch = write_long_term(
            state,
            agent="onboarding_response",
            payload={
                "employee_id": str(employee.get("employee_id") or analysis.get("employee_id") or "EMP"),
                "workflow_type": "onboarding",
                "outcome": outcome,
                "rationale_summary": str(decision.get("rationale") or "")[:400],
                "requires_human_approval": bool(state.get("requires_human_approval")),
            },
        )
        patches.append(ltm_patch)
    except Exception:
        pass

    return node_update(
        "onboarding_response",
        f"Composed onboarding response; status={final_status}; notes={len(notes)}.",
        final_response=response,
        status=final_status,
        **combine_patches(*patches),
    )
