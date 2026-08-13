"""Attendance Decision Agent: produce WorkflowDecision for attendance."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, recall_long_term, search_short_term
from app.models.decision import WorkflowDecision
from app.orchestration.state import WorkflowState


def build_attendance_pending_actions(
    *,
    employee_id: str,
    manager_id: str | None,
    severity: str,
    rationale: str,
    include_manager_notify: bool,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if severity in {"warning", "escalation"}:
        actions.append(
            {
                "type": "create_attendance_review",
                "employee_id": employee_id,
                "reason": rationale,
                "severity": severity,
                "assignee": manager_id or "manager",
            }
        )
        actions.append(
            {
                "type": "send_attendance_warning",
                "employee_id": employee_id,
                "message": (
                    f"Attendance warning: {rationale}"
                    if severity == "warning"
                    else f"Attendance escalation notice: {rationale}"
                ),
            }
        )
        actions.append(
            {
                "type": "update_attendance_status",
                "employee_id": employee_id,
                "status": "under_review" if severity == "escalation" else "warned",
            }
        )
        if include_manager_notify and manager_id:
            actions.append(
                {
                    "type": "notify_employee",
                    "employee_id": manager_id,
                    "message": (
                        f"Attendance review required for employee {employee_id}. {rationale}"
                    ),
                }
            )
    return actions


def attendance_decision_agent(state: WorkflowState) -> dict[str, Any]:
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    employee = state.get("employee_data") or {}
    employee_id = str(
        analysis.get("employee_id")
        or employee.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    manager_id = str(employee.get("manager") or analysis.get("manager") or "") or None
    summary = dict(analysis.get("summary") or {})
    severity = str(policy.get("severity") or "blocked")
    patches: list[dict[str, Any]] = []

    _, notes_patch = search_short_term(state, agent="attendance_decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(
        state,
        agent="attendance_decision",
        employee_id=employee_id or None,
        workflow_type="attendance",
    )
    patches.append(history_patch)

    blockers = list(analysis.get("blockers") or []) + list(policy.get("violations") or [])
    warnings = list(analysis.get("warnings") or []) + list(policy.get("warnings") or [])
    evidence = [
        f"severity={severity}",
        f"attendance_percentage={summary.get('attendance_percentage')}",
        f"late_arrivals={summary.get('late_arrivals')}",
        f"absent_days={summary.get('absent_days')}",
        f"consecutive_absence={summary.get('consecutive_absence')}",
        f"missing_records={summary.get('missing_records')}",
        f"issue_findings={len(analysis.get('issue_findings') or [])}",
    ]
    if history:
        warnings.append("Prior attendance outcomes were available as context only.")

    pending_actions: list[dict[str, Any]] = []

    if analysis.get("scan_mode"):
        findings = list(analysis.get("issue_findings") or [])
        outcome = "recommend"
        executable = False
        requires_human_approval = False
        confidence = 0.86
        rationale = (
            f"Attendance scan completed with {len(findings)} employee(s) flagged "
            "for warning or escalation. No automated write actions were scheduled."
        )
    elif severity == "blocked" or not employee_id:
        outcome = "blocked"
        executable = False
        requires_human_approval = False
        confidence = 0.95
        rationale = (
            "Attendance analysis is blocked due to missing/invalid data or policy blockers: "
            + ("; ".join(blockers) if blockers else "insufficient data.")
        )
    elif severity == "escalation" or policy.get("requires_human_approval"):
        outcome = "escalate"
        executable = False
        requires_human_approval = True
        confidence = 0.9
        rationale = (
            f"Serious attendance issue for {employee_id} "
            f"(pct={summary.get('attendance_percentage')}%, "
            f"consecutive_absence={summary.get('consecutive_absence')}). "
            "Human approval required before review/notification actions."
        )
        if blockers:
            rationale += " " + "; ".join(str(item) for item in blockers)
        pending_actions = [
            {
                "type": "request_human_approval",
                "employee_id": employee_id,
                "severity": severity,
            }
        ]
    elif severity == "warning":
        # Executable low-impact path: warning notify + review create (no discipline).
        outcome = "approve"
        executable = True
        requires_human_approval = False
        confidence = 0.88
        rationale = (
            f"Attendance warning for {employee_id}: "
            f"pct={summary.get('attendance_percentage')}%, "
            f"late_arrivals={summary.get('late_arrivals')}."
        )
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = build_attendance_pending_actions(
            employee_id=employee_id,
            manager_id=manager_id,
            severity="warning",
            rationale=rationale,
            include_manager_notify=True,
        )
    else:
        outcome = "recommend"
        executable = False
        requires_human_approval = False
        confidence = 0.92
        rationale = (
            f"Attendance for {employee_id} is within normal policy thresholds "
            f"(pct={summary.get('attendance_percentage')}%, "
            f"late_arrivals={summary.get('late_arrivals')}). No action required."
        )

    decision = WorkflowDecision(
        outcome=outcome,  # type: ignore[arg-type]
        rationale=rationale,
        executable=executable,
        confidence=confidence,
        requires_human_approval=requires_human_approval,
        entity_refs={
            "employee_id": employee_id or None,
            "manager_id": manager_id,
            "department": employee.get("department") or analysis.get("department"),
            "severity": severity,
            "attendance_percentage": summary.get("attendance_percentage"),
        },
        evidence=evidence,
        blockers=blockers,
        warnings=warnings,
        influenced_by=[item.memory_id for item in history],
    )

    metadata = dict(state.get("metadata") or {})
    metadata["attendance_severity"] = severity
    metadata["attendance_recommendation"] = outcome

    _, memory_patch = append_short_term(
        state,
        agent="attendance_decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; executable={decision.executable}; "
            f"approval={decision.requires_human_approval}; severity={severity}."
        ),
        influenced_decision=bool(history or warnings),
    )
    patches.append(memory_patch)

    return node_update(
        "attendance_decision",
        f"Decision={decision.outcome}; severity={severity}; executable={decision.executable}.",
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        metadata=metadata,
        **combine_patches(*patches),
    )
