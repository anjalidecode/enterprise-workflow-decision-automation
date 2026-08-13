"""Performance Response Agent: summarize outcomes and persist compact LTM."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState


def performance_response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    summary = dict(analysis.get("summary") or {})
    completed = list(state.get("completed_actions") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="performance_response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="performance_response",
        query="performance review process manager responsibilities approval requirements",
        workflow_type="performance",
    )
    patches.append(knowledge_patch)

    status = state.get("status") or "completed"
    if status == "awaiting_human_approval":
        final_status = "awaiting_human_approval"
    elif status == "validation_failed":
        final_status = "validation_failed"
    else:
        final_status = "completed"

    handbook = hits[0].title if hits else "Performance handbook"
    employee_label = (
        f"{employee.get('name') or 'Unknown'} "
        f"({employee.get('employee_id') or analysis.get('employee_id') or 'n/a'})"
    )
    outcome = decision.get("outcome")
    blockers = decision.get("blockers") or analysis.get("blockers") or []
    warnings = decision.get("warnings") or analysis.get("warnings") or []
    findings = analysis.get("support_findings") or []
    strengths = analysis.get("strengths") or []
    concerns = analysis.get("improvement_areas") or []
    skill_gaps = analysis.get("skill_gaps") or []

    reviews = [item for item in completed if item.get("type") == "create_performance_review"]
    plans = [item for item in completed if item.get("type") == "create_improvement_plan"]
    notifications = [item for item in completed if item.get("type") == "notify_employee"]
    status_updates = [item for item in completed if item.get("type") == "update_performance_status"]

    if analysis.get("scan_mode"):
        flagged = ", ".join(
            f"{item.get('employee_id')}({item.get('severity')})" for item in findings
        ) or "none"
        response = (
            f"Performance support scan for {analysis.get('review_period')} "
            f"flagged {len(findings)} employee(s): {flagged}. "
            f"No write actions were executed. Handbook: {handbook}."
        )
    elif final_status == "awaiting_human_approval":
        response = (
            f"Performance for {employee_label} requires human approval before review actions. "
            f"Severity={policy.get('severity')}. "
            f"Goal achievement={summary.get('goal_achievement_pct')}%, "
            f"completed={summary.get('completed_count')}, "
            f"partial={summary.get('partial_count')}, unmet={summary.get('unmet_count')}. "
            f"Strengths: {', '.join(str(item) for item in strengths) or 'none'}. "
            f"Concerns: {', '.join(str(item) for item in concerns) or 'none'}. "
            f"No high-impact employment action will be taken automatically. "
            f"Reason: {decision.get('rationale')}. Handbook: {handbook}."
        )
    elif outcome == "blocked":
        response = (
            f"Performance analysis for {employee_label} is blocked. "
            f"Blockers: {'; '.join(str(item) for item in blockers) or 'none'}. "
            f"No write actions were executed. Handbook: {handbook}."
        )
    elif outcome == "recommend":
        response = (
            f"Strong performance recommendation for {employee_label}. "
            f"Goal achievement={summary.get('goal_achievement_pct')}%, "
            f"completed={summary.get('completed_count')}, "
            f"partial={summary.get('partial_count')}, unmet={summary.get('unmet_count')}. "
            f"Strengths: {', '.join(str(item) for item in strengths) or 'none'}. "
            f"Concerns: {', '.join(str(item) for item in concerns) or 'none'}. "
            f"Recommendation: positive review; no corrective action. Handbook: {handbook}."
        )
    else:
        plan_ids = [str(item.get("plan_id")) for item in plans if item.get("plan_id")]
        review_ids = [str(item.get("review_id")) for item in reviews if item.get("review_id")]
        review_note = f" ({', '.join(review_ids)})" if review_ids else ""
        plan_note = f" ({', '.join(plan_ids)})" if plan_ids else ""
        response = (
            f"Performance actions completed for {employee_label}. "
            f"Goal achievement={summary.get('goal_achievement_pct')}%. "
            f"Strengths: {', '.join(str(item) for item in strengths) or 'none'}. "
            f"Concerns: {', '.join(str(item) for item in concerns) or 'none'}. "
            f"Skill gaps: {', '.join(str(item) for item in skill_gaps) or 'none'}. "
            f"Reviews via tools: {len(reviews)}{review_note}; "
            f"improvement/development plans via tools: {len(plans)}{plan_note}; "
            f"notifications via tools: {len(notifications)}; "
            f"status updates via tools: {len(status_updates)}. "
            f"Warnings: {'; '.join(str(item).rstrip('.') for item in warnings) or 'none'}. "
            f"Handbook: {handbook}."
        )

    try:
        if employee.get("employee_id") or analysis.get("employee_id"):
            _, ltm_patch = write_long_term(
                state,
                agent="performance_response",
                payload={
                    "employee_id": str(
                        employee.get("employee_id") or analysis.get("employee_id") or "EMP"
                    ),
                    "workflow_type": "performance",
                    "outcome": outcome,
                    "severity": policy.get("severity"),
                    "goal_achievement_pct": summary.get("goal_achievement_pct"),
                    "rationale_summary": str(decision.get("rationale") or "")[:400],
                    "requires_human_approval": bool(state.get("requires_human_approval")),
                },
            )
            patches.append(ltm_patch)
    except Exception:
        pass

    return node_update(
        "performance_response",
        f"Composed performance response; status={final_status}; notes={len(notes)}.",
        final_response=response,
        status=final_status,
        **combine_patches(*patches),
    )
