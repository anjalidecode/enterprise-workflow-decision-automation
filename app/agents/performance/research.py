"""Performance Research: employee, records, goals, and prior outcomes via tools only."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def performance_research_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("performance_request") or {}
    entities = state.get("entities") or {}
    employee_id = str(request.get("employee_id") or entities.get("employee_id") or "")
    review_period = str(request.get("review_period") or entities.get("review_period") or "2026-Q2")
    previous_period = str(request.get("previous_period") or "")
    scan_support = bool(request.get("scan_support"))
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    employee: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    goals: list[dict[str, Any]] = []
    previous_records: list[dict[str, Any]] = []
    previous_goals: list[dict[str, Any]] = []
    support_findings: list[dict[str, Any]] = []

    if employee_id:
        emp_result, emp_patch = invoke_tool(
            state,
            agent="performance_research",
            name="get_employee",
            payload={"employee_id": employee_id},
        )
        patches.append(emp_patch)
        if emp_result.success and emp_result.data:
            employee = dict(emp_result.data)
        else:
            errors.append(emp_result.error_message or f"Employee {employee_id} not found.")

        rec_result, rec_patch = invoke_tool(
            state,
            agent="performance_research",
            name="get_performance_records",
            payload={
                "employee_id": employee_id,
                "review_period": review_period,
            },
        )
        patches.append(rec_patch)
        if rec_result.success and rec_result.data:
            records = list(rec_result.data.get("records") or [])
        else:
            errors.append(rec_result.error_message or "get_performance_records failed.")

        goal_result, goal_patch = invoke_tool(
            state,
            agent="performance_research",
            name="get_performance_goals",
            payload={
                "employee_id": employee_id,
                "review_period": review_period,
            },
        )
        patches.append(goal_patch)
        if goal_result.success and goal_result.data:
            goals = list(goal_result.data.get("goals") or [])
        else:
            errors.append(goal_result.error_message or "get_performance_goals failed.")

        if previous_period:
            prev_rec_result, prev_rec_patch = invoke_tool(
                state,
                agent="performance_research",
                name="get_performance_records",
                payload={
                    "employee_id": employee_id,
                    "review_period": previous_period,
                },
            )
            patches.append(prev_rec_patch)
            if prev_rec_result.success and prev_rec_result.data:
                previous_records = list(prev_rec_result.data.get("records") or [])

            prev_goal_result, prev_goal_patch = invoke_tool(
                state,
                agent="performance_research",
                name="get_performance_goals",
                payload={
                    "employee_id": employee_id,
                    "review_period": previous_period,
                },
            )
            patches.append(prev_goal_patch)
            if prev_goal_result.success and prev_goal_result.data:
                previous_goals = list(prev_goal_result.data.get("goals") or [])
    else:
        scan_support = True

    if scan_support:
        support_result, support_patch = invoke_tool(
            state,
            agent="performance_research",
            name="find_performance_support",
            payload={"review_period": review_period},
        )
        patches.append(support_patch)
        if support_result.success and support_result.data:
            support_findings = list(support_result.data.get("findings") or [])
        else:
            errors.append(support_result.error_message or "find_performance_support failed.")

    retrieved = {
        **(state.get("retrieved_data") or {}),
        "performance_records": records,
        "performance_record_count": len(records),
        "performance_goals": goals,
        "performance_goal_count": len(goals),
        "previous_records": previous_records,
        "previous_goals": previous_goals,
        "support_findings": support_findings,
        "performance_scan": scan_support,
        "review_period": review_period,
        "previous_period": previous_period or None,
    }
    entities = merge_entities(
        state,
        employee_id=employee.get("employee_id") or employee_id or None,
        review_period=review_period,
        department=employee.get("department") or None,
    )

    _, memory_patch = append_short_term(
        state,
        agent="performance_research",
        content=(
            f"Retrieved performance records={len(records)} goals={len(goals)} "
            f"for {employee_id or 'scan'}; support_findings={len(support_findings)}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "performance_research",
        (
            f"Researched performance for {employee_id or 'org scan'}: "
            f"{len(records)} record(s), {len(goals)} goal(s), "
            f"{len(support_findings)} support finding(s)."
        ),
        employee_data=employee or state.get("employee_data") or {},
        retrieved_data=retrieved,
        entities=entities,
        errors=errors,
        **combine_patches(*patches),
    )
