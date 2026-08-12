"""Analysis Agent: combine tools, short-term notes, knowledge, and history."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.agents.common import combine_patches, leave_request_from_state, node_update
from app.memory.contracts import MemoryRecord
from app.memory.facade import append_short_term, recall_long_term, search_knowledge, search_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _period(start: Any, days: Any) -> tuple[date, date] | None:
    start_date = _parse_date(start)
    if start_date is None or not isinstance(days, int) or days < 1:
        return None
    return start_date, start_date + timedelta(days=days - 1)


def _overlaps(left: tuple[date, date] | None, right: tuple[date, date] | None) -> bool:
    if left is None or right is None:
        return False
    return left[0] <= right[1] and right[0] <= left[1]


def _history_overlap_warning(
    leave_request: dict[str, Any],
    history: list[MemoryRecord],
) -> str | None:
    current = _period(leave_request.get("start_date"), leave_request.get("days"))
    for record in history:
        meta = record.metadata or {}
        outcome = str(meta.get("outcome") or "")
        if outcome not in {"approved", "pending_approval"}:
            continue
        previous = _period(meta.get("start_date"), meta.get("days"))
        if _overlaps(current, previous):
            return "Previous leave history overlaps the requested period."
    return None


def analysis_agent(state: WorkflowState) -> dict[str, Any]:
    leave_request = leave_request_from_state(state)
    policy_results = state.get("policy_results") or {}
    errors: list[str] = []
    patches: list[dict[str, Any]] = []

    impact_result, impact_patch = invoke_tool(
        state,
        agent="analysis",
        capability="leave.impact",
        payload={
            "employee_id": leave_request.get("employee_id"),
            "days": leave_request.get("days"),
            "leave_type": leave_request.get("leave_type", "annual"),
        },
    )
    patches.append(impact_patch)

    notes, notes_patch = search_short_term(state, agent="analysis")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(state, agent="analysis")
    patches.append(history_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="analysis",
        query="leave process policy concepts manager approval",
    )
    patches.append(knowledge_patch)

    blockers: list[str] = list(policy_results.get("violations", []))
    warnings: list[str] = list(policy_results.get("warnings") or [])
    if not impact_result.success:
        errors.append(impact_result.error_message or "Leave impact calculation failed.")
        impact: dict[str, Any] = {}
        blockers.append("Leave impact could not be calculated.")
    else:
        impact = dict(impact_result.data or {})

    available = impact.get("available_days")
    remaining_after = impact.get("remaining_after")
    sufficient_balance = bool(impact.get("sufficient_balance"))
    employment_active = bool(impact.get("employment_active"))
    employee_found = bool(impact.get("employee_found"))

    if employee_found and not sufficient_balance and not any("balance" in item for item in blockers):
        blockers.append("Insufficient leave balance.")
    if employee_found and not employment_active and not any("active" in item.lower() for item in blockers):
        blockers.append("Employee is not active.")
    if not employee_found:
        blockers.append("No employee record available for analysis.")

    overlap_warning = _history_overlap_warning(leave_request, history)
    if overlap_warning:
        warnings.append(overlap_warning)

    if policy_results.get("requires_human_approval"):
        recommendation = "escalate_for_approval" if not blockers else "reject"
    elif blockers:
        recommendation = "reject"
    else:
        recommendation = "approve"

    analysis_results = {
        "employee_id": leave_request.get("employee_id"),
        "requested_days": leave_request.get("days"),
        "available_days": available,
        "remaining_after": remaining_after,
        "sufficient_balance": sufficient_balance,
        "employment_active": employment_active,
        "requires_human_approval": bool(policy_results.get("requires_human_approval")),
        "blockers": blockers,
        "warnings": warnings,
        "recommendation": recommendation,
        "short_term_notes": len(notes),
        "prior_outcomes": len(history),
        "knowledge_citations": [hit.title for hit in hits],
    }

    _, note_patch = append_short_term(
        state,
        agent="analysis",
        content=f"Analysis recommends {recommendation}; warnings={len(warnings)}.",
    )
    patches.append(note_patch)

    summary = (
        f"Analysis recommendation={recommendation}; "
        f"balance={available}, requested={leave_request.get('days')}, blockers={len(blockers)}."
    )
    return node_update(
        "analysis",
        summary,
        analysis_results=analysis_results,
        errors=errors,
        **combine_patches(*patches),
    )
