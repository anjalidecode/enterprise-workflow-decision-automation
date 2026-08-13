"""Attendance Response Agent: summarize outcomes and persist compact LTM."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState


def attendance_response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    summary = dict(analysis.get("summary") or {})
    completed = list(state.get("completed_actions") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="attendance_response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="attendance_response",
        query="attendance expectations manager review escalation procedure",
        workflow_type="attendance",
    )
    patches.append(knowledge_patch)

    status = state.get("status") or "completed"
    if status == "awaiting_human_approval":
        final_status = "awaiting_human_approval"
    elif status == "validation_failed":
        final_status = "validation_failed"
    else:
        final_status = "completed"

    handbook = hits[0].title if hits else "Attendance handbook"
    employee_label = (
        f"{employee.get('name') or 'Unknown'} "
        f"({employee.get('employee_id') or analysis.get('employee_id') or 'n/a'})"
    )
    outcome = decision.get("outcome")
    blockers = decision.get("blockers") or analysis.get("blockers") or []
    warnings = decision.get("warnings") or analysis.get("warnings") or []
    findings = analysis.get("issue_findings") or []

    reviews = [item for item in completed if item.get("type") == "create_attendance_review"]
    warnings_sent = [item for item in completed if item.get("type") == "send_attendance_warning"]
    notifications = [item for item in completed if item.get("type") == "notify_employee"]
    status_updates = [item for item in completed if item.get("type") == "update_attendance_status"]

    if analysis.get("scan_mode"):
        flagged = ", ".join(
            f"{item.get('employee_id')}({item.get('severity')})" for item in findings
        ) or "none"
        response = (
            f"Attendance scan for {analysis.get('start_date')} to {analysis.get('end_date')} "
            f"flagged {len(findings)} employee(s): {flagged}. "
            f"No write actions were executed. Handbook: {handbook}."
        )
    elif final_status == "awaiting_human_approval":
        response = (
            f"Attendance for {employee_label} requires human approval before review actions. "
            f"Severity={policy.get('severity')}. "
            f"Present={summary.get('present_days')}, absent={summary.get('absent_days')}, "
            f"late={summary.get('late_arrivals')}, pct={summary.get('attendance_percentage')}%. "
            f"Reason: {decision.get('rationale')}. Handbook: {handbook}."
        )
    elif outcome == "blocked":
        response = (
            f"Attendance analysis for {employee_label} is blocked. "
            f"Blockers: {'; '.join(str(item) for item in blockers) or 'none'}. "
            f"Missing records: {summary.get('missing_records', 'n/a')}. "
            f"No write actions were executed. Handbook: {handbook}."
        )
    elif outcome == "recommend":
        response = (
            f"Attendance for {employee_label} is within normal thresholds. "
            f"Present={summary.get('present_days')}, absent={summary.get('absent_days')}, "
            f"late={summary.get('late_arrivals')}, early={summary.get('early_departures')}, "
            f"pct={summary.get('attendance_percentage')}%. "
            f"Recommendation: no action. Handbook: {handbook}."
        )
    else:
        response = (
            f"Attendance actions completed for {employee_label}. "
            f"Metrics: present={summary.get('present_days')}, absent={summary.get('absent_days')}, "
            f"late={summary.get('late_arrivals')}, pct={summary.get('attendance_percentage')}%. "
            f"Reviews via tools: {len(reviews)}; warnings via tools: {len(warnings_sent)}; "
            f"manager notifications via tools: {len(notifications)}; "
            f"status updates via tools: {len(status_updates)}. "
            f"Warnings: {'; '.join(str(item) for item in warnings) or 'none'}. "
            f"Handbook: {handbook}."
        )

    try:
        if employee.get("employee_id") or analysis.get("employee_id"):
            _, ltm_patch = write_long_term(
                state,
                agent="attendance_response",
                payload={
                    "employee_id": str(
                        employee.get("employee_id") or analysis.get("employee_id") or "EMP"
                    ),
                    "workflow_type": "attendance",
                    "outcome": outcome,
                    "severity": policy.get("severity"),
                    "attendance_percentage": summary.get("attendance_percentage"),
                    "rationale_summary": str(decision.get("rationale") or "")[:400],
                    "requires_human_approval": bool(state.get("requires_human_approval")),
                },
            )
            patches.append(ltm_patch)
    except Exception:
        pass

    return node_update(
        "attendance_response",
        f"Composed attendance response; status={final_status}; notes={len(notes)}.",
        final_response=response,
        status=final_status,
        **combine_patches(*patches),
    )
