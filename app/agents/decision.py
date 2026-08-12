"""Decision Agent: produce an approve / reject / pending-approval outcome."""

from __future__ import annotations

from typing import Any

from app.agents.common import leave_request_from_state, node_update
from app.models.leave import LeaveDecision
from app.orchestration.state import WorkflowState


def decision_agent(state: WorkflowState) -> dict[str, Any]:
    analysis = state.get("analysis_results") or {}
    leave_request = leave_request_from_state(state)
    recommendation = analysis.get("recommendation", "reject")
    blockers = list(analysis.get("blockers") or [])

    if recommendation == "approve":
        decision = LeaveDecision(
            outcome="approve",
            rationale="Request satisfies leave balance, employment status, and policy limits.",
            executable=True,
            employee_id=leave_request.get("employee_id"),
            requested_days=leave_request.get("days"),
            confidence=0.92,
        )
        pending_actions = [
            {
                "type": "simulate_leave_balance_update",
                "employee_id": leave_request.get("employee_id"),
                "days": leave_request.get("days"),
                "leave_type": leave_request.get("leave_type", "annual"),
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
    )
