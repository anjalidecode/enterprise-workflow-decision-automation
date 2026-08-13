"""Attendance Analysis: compute metrics and patterns via summary tool."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def attendance_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    employee = state.get("employee_data") or {}
    request = (state.get("metadata") or {}).get("attendance_request") or {}
    employee_id = str(
        employee.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    start_date = str(retrieved.get("start_date") or request.get("start_date") or "2026-07-01")
    end_date = str(retrieved.get("end_date") or request.get("end_date") or "2026-07-31")
    records = list(retrieved.get("attendance_records") or [])
    issue_findings = list(retrieved.get("attendance_issue_findings") or [])
    scan = bool(retrieved.get("attendance_scan"))
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    summary: dict[str, Any] = {}

    _, knowledge_patch = search_knowledge(
        state,
        agent="attendance_analysis",
        query="attendance expectations late arrival absence reporting",
        workflow_type="attendance",
    )
    patches.append(knowledge_patch)

    if employee_id:
        result, patch = invoke_tool(
            state,
            agent="attendance_analysis",
            name="calculate_attendance_summary",
            payload={
                "employee_id": employee_id,
                "start_date": start_date,
                "end_date": end_date,
                "records": records,
            },
        )
        patches.append(patch)
        if result.success and result.data:
            summary = dict(result.data)
        else:
            errors.append(result.error_message or "calculate_attendance_summary failed.")

    patterns: list[str] = []
    if summary:
        if int(summary.get("late_arrivals") or 0) >= 2:
            patterns.append("repeated_lateness")
        if int(summary.get("consecutive_absence") or 0) >= 2:
            patterns.append("consecutive_absence")
        if int(summary.get("missing_records") or 0) > 0:
            patterns.append("missing_records")
        if float(summary.get("attendance_percentage") or 0) < 90:
            patterns.append("below_normal_attendance")

    if not employee_id and scan:
        recommendation = "scan_report"
    elif not employee_id:
        recommendation = "blocked"
    elif not records and int(summary.get("missing_records") or 0) > 0:
        recommendation = "blocked"
    else:
        recommendation = "pending_policy"

    analysis = {
        "employee_id": employee_id or None,
        "department": employee.get("department") or retrieved.get("department"),
        "manager": employee.get("manager"),
        "start_date": start_date,
        "end_date": end_date,
        "summary": summary,
        "patterns": patterns,
        "issue_findings": issue_findings,
        "scan_mode": scan and not employee_id,
        "recommendation": recommendation,
        "blockers": (
            ["No attendance records available for analysis."]
            if employee_id and not records
            else []
        ),
        "warnings": [],
    }

    _, memory_patch = append_short_term(
        state,
        agent="attendance_analysis",
        content=(
            f"Attendance analysis employee={employee_id or 'scan'}; "
            f"pct={summary.get('attendance_percentage')}; "
            f"late={summary.get('late_arrivals')}; "
            f"absent={summary.get('absent_days')}; patterns={patterns}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "attendance_analysis",
        (
            f"Analyzed attendance; pct={summary.get('attendance_percentage', 'n/a')}; "
            f"patterns={len(patterns)}; findings={len(issue_findings)}."
        ),
        analysis_results=analysis,
        errors=errors,
        **combine_patches(*patches),
    )
