"""Performance Decision Agent: produce WorkflowDecision for performance."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, recall_long_term, search_short_term
from app.models.decision import WorkflowDecision
from app.orchestration.state import WorkflowState


def build_performance_pending_actions(
    *,
    employee_id: str,
    manager_id: str | None,
    severity: str,
    rationale: str,
    review_period: str,
    plan_type: str | None,
    focus_areas: list[str],
    include_manager_notify: bool,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if severity not in {"development", "concern", "escalation"}:
        return actions

    actions.append(
        {
            "type": "create_performance_review",
            "employee_id": employee_id,
            "reason": rationale,
            "severity": severity,
            "assignee": manager_id or "manager",
            "review_period": review_period,
        }
    )
    if plan_type:
        actions.append(
            {
                "type": "create_improvement_plan",
                "employee_id": employee_id,
                "reason": rationale,
                "plan_type": plan_type,
                "focus_areas": focus_areas,
                "review_period": review_period,
            }
        )
    actions.append(
        {
            "type": "notify_employee",
            "employee_id": employee_id,
            "message": (
                f"Performance {plan_type or 'review'} recommendation for {review_period}: {rationale}"
            ),
        }
    )
    actions.append(
        {
            "type": "update_performance_status",
            "employee_id": employee_id,
            "status": "under_review" if severity == "escalation" else "review_recommended",
            "review_period": review_period,
        }
    )
    if include_manager_notify and manager_id:
        actions.append(
            {
                "type": "notify_employee",
                "employee_id": manager_id,
                "message": (
                    f"Performance review required for employee {employee_id} "
                    f"({review_period}). {rationale}"
                ),
            }
        )
    return actions


def performance_decision_agent(state: WorkflowState) -> dict[str, Any]:
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
    review_period = str(analysis.get("review_period") or "2026-Q2")
    summary = dict(analysis.get("summary") or {})
    severity = str(policy.get("severity") or "blocked")
    plan_type = policy.get("plan_type")
    focus_areas = list(analysis.get("skill_gaps") or analysis.get("improvement_areas") or [])
    patches: list[dict[str, Any]] = []

    _, notes_patch = search_short_term(state, agent="performance_decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(
        state,
        agent="performance_decision",
        employee_id=employee_id or None,
        workflow_type="performance",
    )
    patches.append(history_patch)

    blockers = list(analysis.get("blockers") or []) + list(policy.get("violations") or [])
    warnings = list(analysis.get("warnings") or []) + list(policy.get("warnings") or [])
    evidence = [
        f"severity={severity}",
        f"goal_achievement_pct={summary.get('goal_achievement_pct')}",
        f"completed={summary.get('completed_count')}",
        f"partial={summary.get('partial_count')}",
        f"unmet={summary.get('unmet_count')}",
        f"skill_gaps={analysis.get('skill_gaps') or []}",
        f"support_findings={len(analysis.get('support_findings') or [])}",
    ]
    if history:
        warnings.append("Prior performance outcomes were available as context only.")

    pending_actions: list[dict[str, Any]] = []

    if analysis.get("scan_mode"):
        findings = list(analysis.get("support_findings") or [])
        outcome = "recommend"
        executable = False
        requires_human_approval = False
        confidence = 0.86
        rationale = (
            f"Performance support scan completed with {len(findings)} employee(s) flagged. "
            "No automated write actions were scheduled."
        )
    elif severity == "blocked" or not employee_id:
        outcome = "blocked"
        executable = False
        requires_human_approval = False
        confidence = 0.95
        rationale = (
            "Performance analysis is blocked due to missing/invalid data or policy blockers: "
            + ("; ".join(str(item) for item in blockers) if blockers else "insufficient data.")
        )
    elif severity == "escalation" or policy.get("requires_human_approval"):
        outcome = "escalate"
        executable = False
        requires_human_approval = True
        confidence = 0.9
        rationale = (
            f"Serious performance concern for {employee_id} "
            f"(goal achievement={summary.get('goal_achievement_pct')}%, "
            f"unmet={summary.get('unmet_count')}). "
            "Human approval required before review or improvement-plan actions. "
            "No termination, demotion, or disciplinary action will be taken automatically."
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
    elif severity in {"development", "concern"}:
        outcome = "ready"
        executable = True
        requires_human_approval = False
        confidence = 0.88
        if severity == "development":
            rationale = (
                f"Mixed/development performance for {employee_id}: "
                f"goal achievement={summary.get('goal_achievement_pct')}%. "
                "Recommend manager review and a development plan."
            )
        else:
            rationale = (
                f"Performance concern for {employee_id}: "
                f"goal achievement={summary.get('goal_achievement_pct')}%. "
                "Recommend manager review and a performance improvement plan."
            )
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = build_performance_pending_actions(
            employee_id=employee_id,
            manager_id=manager_id,
            severity=severity,
            rationale=rationale,
            review_period=review_period,
            plan_type=str(plan_type) if plan_type else "development",
            focus_areas=focus_areas,
            include_manager_notify=True,
        )
    else:
        outcome = "recommend"
        executable = False
        requires_human_approval = False
        confidence = 0.92
        rationale = (
            f"Strong performance for {employee_id} "
            f"(goal achievement={summary.get('goal_achievement_pct')}%). "
            "Positive review recommendation; no corrective action required."
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
            "review_period": review_period,
            "plan_type": plan_type,
            "goal_achievement_pct": summary.get("goal_achievement_pct"),
            "focus_areas": focus_areas,
        },
        evidence=evidence,
        blockers=blockers,
        warnings=warnings,
        influenced_by=[item.memory_id for item in history],
    )

    metadata = dict(state.get("metadata") or {})
    metadata["performance_severity"] = severity
    metadata["performance_recommendation"] = outcome
    metadata["performance_plan_type"] = plan_type

    _, memory_patch = append_short_term(
        state,
        agent="performance_decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; executable={decision.executable}; "
            f"approval={decision.requires_human_approval}; severity={severity}."
        ),
        influenced_decision=bool(history or warnings),
    )
    patches.append(memory_patch)

    return node_update(
        "performance_decision",
        f"Decision={decision.outcome}; severity={severity}; executable={decision.executable}.",
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        metadata=metadata,
        **combine_patches(*patches),
    )
