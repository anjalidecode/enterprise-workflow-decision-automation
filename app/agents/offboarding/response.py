"""Offboarding Response Agent: summarize outcomes and persist compact LTM."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState


def offboarding_response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    completed = list(state.get("completed_actions") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="offboarding_response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="offboarding_response",
        query="resignation process exit checklist asset return access revocation",
        workflow_type="offboarding",
    )
    patches.append(knowledge_patch)

    status = state.get("status") or "completed"
    if status == "awaiting_human_approval":
        final_status = "awaiting_human_approval"
    elif status == "validation_failed":
        final_status = "validation_failed"
    else:
        final_status = "completed"

    handbook = hits[0].title if hits else "Offboarding handbook"
    employee_label = (
        f"{employee.get('name') or 'Unknown'} "
        f"({employee.get('employee_id') or analysis.get('employee_id') or 'n/a'})"
    )
    outcome = decision.get("outcome")
    blockers = decision.get("blockers") or analysis.get("blockers") or []
    warnings = decision.get("warnings") or analysis.get("warnings") or []
    checklist = analysis.get("checklist") or {}
    pending_tasks = analysis.get("pending_tasks") or checklist.get("pending_tasks") or []
    outstanding = analysis.get("outstanding_assets") or []
    handover = analysis.get("handover") or {}

    tasks = [item for item in completed if item.get("type") == "create_offboarding_task"]
    asset_returns = [item for item in completed if item.get("type") == "request_asset_return"]
    handovers = [item for item in completed if item.get("type") == "create_offboarding_handover"]
    interviews = [item for item in completed if item.get("type") == "schedule_exit_interview"]
    access_requests = [
        item for item in completed if item.get("type") == "create_access_revoke_request"
    ]
    notifications = [item for item in completed if item.get("type") == "notify_employee"]
    status_updates = [
        item for item in completed if item.get("type") == "update_offboarding_status"
    ]

    if final_status == "awaiting_human_approval":
        response = (
            f"Offboarding for {employee_label} requires human approval before privileged "
            f"access-revocation request/finalization. "
            f"Exit type: {analysis.get('exit_type') or 'n/a'}; "
            f"notice/last working day: {analysis.get('last_working_day') or 'n/a'}; "
            f"checklist pending: {', '.join(str(item) for item in pending_tasks) or 'none'}; "
            f"outstanding assets: {len(outstanding)}; "
            f"handover status: {handover.get('handover_status') or 'n/a'}; "
            f"approval_level={policy.get('approval_level')}. "
            f"No privileged write actions were executed. "
            f"Reason: {decision.get('rationale')}. Handbook: {handbook}."
        )
    elif outcome == "blocked":
        response = (
            f"Offboarding for {employee_label} is blocked. "
            f"Exit type: {analysis.get('exit_type') or 'n/a'}; "
            f"notice/last working day: {analysis.get('last_working_day') or 'n/a'}; "
            f"Blockers: {'; '.join(str(item) for item in blockers) or 'none'}. "
            f"No offboarding write actions were executed. Handbook: {handbook}."
        )
    elif outcome == "recommend":
        response = (
            f"Offboarding recommendations for {employee_label}. "
            f"Exit type: {analysis.get('exit_type') or 'n/a'}; "
            f"checklist pending: {', '.join(str(item) for item in pending_tasks) or 'none'}; "
            f"outstanding assets: {len(outstanding)}. "
            f"No automated write actions were executed. Handbook: {handbook}."
        )
    else:
        task_note = f" ({len(tasks)})" if tasks else ""
        asset_note = f" ({len(asset_returns)})" if asset_returns else ""
        handover_note = f" ({len(handovers)})" if handovers else ""
        interview_claim = (
            f"Exit interview scheduled via tools: {len(interviews)}."
            if interviews
            else "No exit interview scheduling confirmed by tools."
        )
        access_claim = (
            f"Access-revocation requests via tools: {len(access_requests)} "
            f"(request only; not automatic revocation)."
            if access_requests
            else "No access-revocation request confirmed by tools."
        )
        response = (
            f"Offboarding preparation completed for {employee_label}. "
            f"Exit type: {analysis.get('exit_type') or 'n/a'}; "
            f"notice/last working day: {analysis.get('last_working_day') or 'n/a'}; "
            f"checklist pending at decision time: "
            f"{', '.join(str(item) for item in pending_tasks) or 'none'}; "
            f"checklist tasks via tools: {len(tasks)}{task_note}; "
            f"asset-return requests via tools: {len(asset_returns)}{asset_note}; "
            f"handover tasks via tools: {len(handovers)}{handover_note}; "
            f"{interview_claim} {access_claim} "
            f"Notifications via tools: {len(notifications)}; "
            f"status updates via tools: {len(status_updates)}. "
            f"Approval status: {outcome}; "
            f"Warnings: {'; '.join(str(item).rstrip('.') for item in warnings) or 'none'}. "
            f"Employment was not terminated automatically. Handbook: {handbook}."
        )

    try:
        if employee.get("employee_id") or analysis.get("employee_id"):
            _, ltm_patch = write_long_term(
                state,
                agent="offboarding_response",
                payload={
                    "employee_id": str(
                        employee.get("employee_id") or analysis.get("employee_id") or "EMP"
                    ),
                    "workflow_type": "offboarding",
                    "outcome": outcome,
                    "exit_type": analysis.get("exit_type"),
                    "last_working_day": analysis.get("last_working_day"),
                    "checklist_summary": {
                        "pending": list(pending_tasks)[:10],
                        "completed_writes": len(tasks),
                    },
                    "rationale_summary": str(decision.get("rationale") or "")[:400],
                    "requires_human_approval": bool(state.get("requires_human_approval")),
                    "access_requests": len(access_requests),
                },
            )
            patches.append(ltm_patch)
    except Exception:
        pass

    return node_update(
        "offboarding_response",
        f"Composed offboarding response; status={final_status}; notes={len(notes)}.",
        final_response=response,
        status=final_status,
        **combine_patches(*patches),
    )
