"""Response Agent: compose the final response and write long-term outcome memory."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState

_OUTCOME_LABELS = {
    "approve": "approved",
    "reject": "rejected",
    "pending_approval": "pending_approval",
    "escalate": "escalated",
    "recommend": "recommended",
}


def response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    outcome = decision.get("outcome", "unknown")
    employee = state.get("employee_data") or {}
    leave_request = (state.get("metadata") or {}).get("leave_request") or {}
    validation = (state.get("metadata") or {}).get("validation") or {}
    analysis = state.get("analysis_results") or {}
    name = employee.get("name") or leave_request.get("employee_id") or "the employee"
    days = leave_request.get("days")
    start_date = leave_request.get("start_date")
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="response",
        query="leave request guidance manager approval",
    )
    patches.append(knowledge_patch)

    citation = f" Handbook: {hits[0].title}." if hits else ""
    warnings = list(analysis.get("warnings") or [])
    warning_text = f" Note: {warnings[0]}" if warnings else ""

    if not validation.get("passed", True) and validation.get("issues"):
        status = "failed"
        final_response = (
            "Leave workflow could not be completed because validation failed: "
            + "; ".join(validation["issues"])
        )
    elif state.get("requires_human_approval"):
        status = "awaiting_human_approval"
        final_response = (
            f"Leave request for {name} ({days} day(s) from {start_date}) "
            "requires human approval before any leave action is executed. "
            f"Reason: {decision.get('rationale', 'policy threshold reached.')}"
            f"{citation}"
        )
    elif outcome == "approve":
        status = "completed"
        balances = employee.get("leave_balances") or {}
        remaining = balances.get(leave_request.get("leave_type", "annual"))
        final_response = (
            f"Leave approved for {name}: {days} day(s) starting {start_date}. "
            f"Simulated remaining annual balance: {remaining}."
            f"{warning_text}{citation}"
        )
    elif outcome == "reject":
        status = "completed"
        final_response = (
            f"Leave request for {name} was rejected. "
            f"Reason: {decision.get('rationale', 'policy requirements were not met.')}"
            f"{citation}"
        )
    else:
        status = "failed" if state.get("errors") else "completed"
        final_response = decision.get("rationale") or "Workflow finished without an executable decision."

    long_term_outcome = _OUTCOME_LABELS.get(str(outcome))
    employee_id = leave_request.get("employee_id") or employee.get("employee_id")
    if long_term_outcome and employee_id and status in {"completed", "awaiting_human_approval"}:
        _, long_term_patch = write_long_term(
            state,
            agent="response",
            payload={
                "employee_id": employee_id,
                "workflow_type": state.get("workflow_type") or "leave_attendance",
                "outcome": long_term_outcome,
                "days": days,
                "start_date": start_date,
                "rationale_summary": str(decision.get("rationale") or final_response)[:400],
                "requires_human_approval": bool(state.get("requires_human_approval")),
                "workflow_id": state.get("workflow_id"),
            },
        )
        patches.append(long_term_patch)

    summary = f"Composed final response; status={status}; notes={len(notes)}."
    return node_update(
        "response",
        summary,
        status=status,
        final_response=final_response,
        **combine_patches(*patches),
    )
