"""Training Response Agent: summarize outcomes and persist compact LTM."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState


def training_response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    completed = list(state.get("completed_actions") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="training_response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="training_response",
        query="training request procedure manager approval course selection",
        workflow_type="training",
    )
    patches.append(knowledge_patch)

    status = state.get("status") or "completed"
    if status == "awaiting_human_approval":
        final_status = "awaiting_human_approval"
    elif status == "validation_failed":
        final_status = "validation_failed"
    else:
        final_status = "completed"

    handbook = hits[0].title if hits else "Training handbook"
    employee_label = (
        f"{employee.get('name') or 'Unknown'} "
        f"({employee.get('employee_id') or analysis.get('employee_id') or 'n/a'})"
    )
    outcome = decision.get("outcome")
    blockers = decision.get("blockers") or analysis.get("blockers") or []
    warnings = decision.get("warnings") or analysis.get("warnings") or []
    skill_gaps = analysis.get("skill_gaps") or []
    gap_labels = [
        str(item.get("skill") or item) for item in skill_gaps
    ]
    primary = dict(analysis.get("recommended_course") or {})
    alternatives = list(analysis.get("alternative_courses") or [])
    reasons = list(analysis.get("recommendation_reasons") or [])

    plans = [item for item in completed if item.get("type") == "create_training_plan"]
    enrollments = [item for item in completed if item.get("type") == "create_training_enrollment"]
    notifications = [item for item in completed if item.get("type") == "notify_employee"]
    status_updates = [item for item in completed if item.get("type") == "update_training_status"]

    if final_status == "awaiting_human_approval":
        response = (
            f"Training recommendation for {employee_label} requires human approval before enrollment. "
            f"Skill gaps: {', '.join(gap_labels) or 'none'}. "
            f"Recommended: {primary.get('title') or 'n/a'} ({primary.get('course_id') or 'n/a'}), "
            f"cost={primary.get('cost', 'n/a')}, approval_level={policy.get('approval_level')}. "
            f"Alternatives: "
            f"{', '.join(str(item.get('course_id')) for item in alternatives) or 'none'}. "
            f"No enrollment was executed. Reason: {decision.get('rationale')}. Handbook: {handbook}."
        )
    elif outcome == "blocked":
        response = (
            f"Training recommendation for {employee_label} is blocked. "
            f"Skill gaps: {', '.join(gap_labels) or 'none'}. "
            f"Blockers: {'; '.join(str(item) for item in blockers) or 'none'}. "
            f"No enrollment was executed. Handbook: {handbook}."
        )
    elif outcome == "recommend":
        response = (
            f"Training recommendations for {employee_label}. "
            f"Skill gaps: {', '.join(gap_labels) or 'none'}. "
            f"Recommended: {primary.get('title') or 'n/a'} ({primary.get('course_id') or 'n/a'}). "
            f"Reasons: {'; '.join(reasons) or 'n/a'}. "
            f"Alternatives: "
            f"{', '.join(str(item.get('course_id')) for item in alternatives) or 'none'}. "
            f"No enrollment was executed. Handbook: {handbook}."
        )
    else:
        plan_ids = [str(item.get("plan_id")) for item in plans if item.get("plan_id")]
        enrollment_ids = [
            str(item.get("enrollment_id")) for item in enrollments if item.get("enrollment_id")
        ]
        plan_note = f" ({', '.join(plan_ids)})" if plan_ids else ""
        enroll_note = f" ({', '.join(enrollment_ids)})" if enrollment_ids else ""
        enrolled = bool(enrollments)
        enrollment_claim = (
            f"Enrollment via tools: {len(enrollments)}{enroll_note}."
            if enrolled
            else "No enrollment was confirmed by tools."
        )
        response = (
            f"Training actions completed for {employee_label}. "
            f"Skill gaps: {', '.join(gap_labels) or 'none'}. "
            f"Recommended: {primary.get('title') or 'n/a'} ({primary.get('course_id') or 'n/a'}). "
            f"Reasons: {'; '.join(reasons) or 'n/a'}. "
            f"Training plans via tools: {len(plans)}{plan_note}. "
            f"{enrollment_claim} "
            f"Notifications via tools: {len(notifications)}; "
            f"status updates via tools: {len(status_updates)}. "
            f"Warnings: {'; '.join(str(item).rstrip('.') for item in warnings) or 'none'}. "
            f"Handbook: {handbook}."
        )

    try:
        if employee.get("employee_id") or analysis.get("employee_id"):
            _, ltm_patch = write_long_term(
                state,
                agent="training_response",
                payload={
                    "employee_id": str(
                        employee.get("employee_id") or analysis.get("employee_id") or "EMP"
                    ),
                    "workflow_type": "training",
                    "outcome": outcome,
                    "course_id": primary.get("course_id"),
                    "skill_gaps": gap_labels[:10],
                    "rationale_summary": str(decision.get("rationale") or "")[:400],
                    "requires_human_approval": bool(state.get("requires_human_approval")),
                    "enrolled": bool(enrollments),
                },
            )
            patches.append(ltm_patch)
    except Exception:
        pass

    return node_update(
        "training_response",
        f"Composed training response; status={final_status}; notes={len(notes)}.",
        final_response=response,
        status=final_status,
        **combine_patches(*patches),
    )
