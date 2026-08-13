"""Attendance Research: employee + attendance records via tools only."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def attendance_research_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("attendance_request") or {}
    entities = state.get("entities") or {}
    employee_id = str(request.get("employee_id") or entities.get("employee_id") or "")
    start_date = str(request.get("start_date") or entities.get("start_date") or "2026-07-01")
    end_date = str(request.get("end_date") or entities.get("end_date") or "2026-07-31")
    department = str(request.get("department") or entities.get("department") or "")
    scan_issues = bool(request.get("scan_issues"))
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    employee: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    issue_findings: list[dict[str, Any]] = []

    if employee_id:
        emp_result, emp_patch = invoke_tool(
            state,
            agent="attendance_research",
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
            agent="attendance_research",
            name="get_attendance_records",
            payload={
                "employee_id": employee_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        patches.append(rec_patch)
        if rec_result.success and rec_result.data:
            records = list(rec_result.data.get("records") or [])
        else:
            errors.append(rec_result.error_message or "get_attendance_records failed.")
    else:
        scan_issues = True

    if scan_issues:
        issues_result, issues_patch = invoke_tool(
            state,
            agent="attendance_research",
            name="find_attendance_issues",
            payload={
                "start_date": start_date,
                "end_date": end_date,
                "department": department,
            },
        )
        patches.append(issues_patch)
        if issues_result.success and issues_result.data:
            issue_findings = list(issues_result.data.get("findings") or [])
        else:
            errors.append(issues_result.error_message or "find_attendance_issues failed.")

    retrieved = {
        **(state.get("retrieved_data") or {}),
        "attendance_records": records,
        "attendance_record_count": len(records),
        "attendance_issue_findings": issue_findings,
        "attendance_scan": scan_issues,
        "start_date": start_date,
        "end_date": end_date,
        "department": department or None,
    }
    entities = merge_entities(
        state,
        employee_id=employee.get("employee_id") or employee_id or None,
        department=employee.get("department") or department or None,
        start_date=start_date,
        end_date=end_date,
    )

    _, memory_patch = append_short_term(
        state,
        agent="attendance_research",
        content=(
            f"Retrieved attendance records={len(records)} for {employee_id or 'scan'}; "
            f"issue_findings={len(issue_findings)}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "attendance_research",
        (
            f"Researched attendance for {employee_id or department or 'org scan'}: "
            f"{len(records)} record(s), {len(issue_findings)} issue finding(s)."
        ),
        employee_data=employee or state.get("employee_data") or {},
        retrieved_data=retrieved,
        entities=entities,
        errors=errors,
        **combine_patches(*patches),
    )
