"""Decision Agent: produce an outcome from tools/policy, with memory as context only."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, leave_request_from_state, node_update
from app.memory.facade import append_short_term, recall_long_term, search_knowledge, search_short_term
from app.models.leave import LeaveDecision
from app.orchestration.state import WorkflowState


def decision_agent(state: WorkflowState) -> dict[str, Any]:
    analysis = state.get("analysis_results") or {}
    policy_results = state.get("policy_results") or {}
    leave_request = leave_request_from_state(state)
    recommendation = analysis.get("recommendation", "reject")
    blockers = list(analysis.get("blockers") or [])
    warnings = list(analysis.get("warnings") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(state, agent="decision")
    patches.append(history_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="decision",
        query="manager approval for long leave",
    )
    patches.append(knowledge_patch)

    memory_influenced = bool(warnings or history or hits or notes)
    # Structured policy/tools remain authoritative. Memory may only adjust confidence.
    if recommendation == "approve" and (policy_results.get("violations") or blockers):
        recommendation = "reject"

    if recommendation == "approve":
        confidence = 0.80 if warnings else 0.92
        rationale = "Request satisfies leave balance, employment status, and policy limits."
        if warnings:
            rationale += " Warnings: " + "; ".join(warnings)
        decision = LeaveDecision(
            outcome="approve",
            rationale=rationale,
            executable=True,
            employee_id=leave_request.get("employee_id"),
            requested_days=leave_request.get("days"),
            confidence=confidence,
        )
        pending_actions = [
            {
                "type": "update_leave_balance",
                "employee_id": leave_request.get("employee_id"),
                "days": leave_request.get("days"),
                "leave_type": leave_request.get("leave_type", "annual"),
                "start_date": leave_request.get("start_date"),
            },
            {
                "type": "notify_employee",
                "employee_id": leave_request.get("employee_id"),
                "message": "Leave request approved.",
            },
        ]
        requires_human_approval = False
    elif recommendation == "escalate_for_approval":
        decision = LeaveDecision(
            outcome="pending_approval",
            rationale=(
                "Policy requires human approval before this leave request can be executed. "
                + (f"Blockers: {'; '.join(blockers)}" if blockers else "")
            ).strip(),
            executable=False,
            employee_id=leave_request.get("employee_id"),
            requested_days=leave_request.get("days"),
            confidence=0.78,
        )
        pending_actions = [
            {
                "type": "request_human_approval",
                "employee_id": leave_request.get("employee_id"),
                "days": leave_request.get("days"),
            }
        ]
        requires_human_approval = True
    else:
        reason = "; ".join(blockers) if blockers else "Leave request does not meet policy requirements."
        decision = LeaveDecision(
            outcome="reject",
            rationale=reason,
            executable=False,
            employee_id=leave_request.get("employee_id"),
            requested_days=leave_request.get("days"),
            confidence=0.95,
        )
        pending_actions = []
        requires_human_approval = False

    influence_ids = [item.memory_id for item in history] + [hit.document_id for hit in hits]
    _, influence_patch = append_short_term(
        state,
        agent="decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; memory_context={len(influence_ids)}; "
            f"warnings={len(warnings)}. Policy/tools remain authoritative."
        ),
        influenced_decision=memory_influenced and bool(warnings or history),
    )
    patches.append(influence_patch)

    summary = (
        f"Decision={decision.outcome}; executable={decision.executable}; "
        f"confidence={decision.confidence:.2f}."
    )
    return node_update(
        "decision",
        summary,
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        **combine_patches(*patches),
    )
