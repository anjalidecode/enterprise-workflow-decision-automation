"""Goal Analysis: compare actuals against goals and produce structured evidence."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def goal_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    employee = state.get("employee_data") or {}
    request = (state.get("metadata") or {}).get("performance_request") or {}
    employee_id = str(
        employee.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    review_period = str(
        retrieved.get("review_period") or request.get("review_period") or "2026-Q2"
    )
    records = list(retrieved.get("performance_records") or [])
    goals = list(retrieved.get("performance_goals") or [])
    scan = bool(retrieved.get("performance_scan"))
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    summary: dict[str, Any] = {}

    if employee_id:
        result, patch = invoke_tool(
            state,
            agent="goal_analysis",
            name="calculate_performance_summary",
            payload={
                "employee_id": employee_id,
                "review_period": review_period,
                "records": records,
                "goals": goals,
            },
        )
        patches.append(patch)
        if result.success and result.data:
            summary = dict(result.data)
        else:
            errors.append(result.error_message or "calculate_performance_summary failed.")

    completed = list(summary.get("completed_goals") or [])
    partial = list(summary.get("partial_goals") or [])
    unmet = list(summary.get("unmet_goals") or [])
    evidence = [
        f"goal_achievement_pct={summary.get('goal_achievement_pct')}",
        f"completed={len(completed)}",
        f"partial={len(partial)}",
        f"unmet={len(unmet)}",
    ]
    for row in completed + partial + unmet:
        evidence.append(
            f"{row.get('status')}:{row.get('goal_id')}={row.get('achievement_pct')}%"
        )

    goal_analysis = {
        "employee_id": employee_id or None,
        "review_period": review_period,
        "summary": summary,
        "completed_goals": completed,
        "partial_goals": partial,
        "unmet_goals": unmet,
        "goal_achievement_pct": summary.get("goal_achievement_pct"),
        "evidence": evidence,
        "scan_mode": scan and not employee_id,
        "blockers": (
            ["No performance goals available for analysis."]
            if employee_id and not goals
            else []
        ),
    }

    retrieved = {
        **retrieved,
        "goal_analysis": goal_analysis,
        "performance_summary": summary,
    }

    _, memory_patch = append_short_term(
        state,
        agent="goal_analysis",
        content=(
            f"Goal analysis employee={employee_id or 'scan'}; "
            f"achievement={summary.get('goal_achievement_pct')}; "
            f"completed={len(completed)}; partial={len(partial)}; unmet={len(unmet)}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "goal_analysis",
        (
            f"Compared goals for {employee_id or 'scan'}; "
            f"achievement={summary.get('goal_achievement_pct', 'n/a')}%."
        ),
        retrieved_data=retrieved,
        analysis_results=goal_analysis,
        errors=errors,
        **combine_patches(*patches),
    )
