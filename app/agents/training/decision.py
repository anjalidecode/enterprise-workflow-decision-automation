"""Training Decision Agent: produce WorkflowDecision for training."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, recall_long_term, search_short_term
from app.models.decision import WorkflowDecision
from app.orchestration.state import WorkflowState


def build_training_pending_actions(
    *,
    employee_id: str,
    manager_id: str | None,
    primary_course: dict[str, Any] | None,
    alternative_courses: list[dict[str, Any]],
    skill_gaps: list[str],
    rationale: str,
    include_manager_notify: bool,
) -> list[dict[str, Any]]:
    if not employee_id or not primary_course:
        return []

    course_id = str(primary_course.get("course_id") or "")
    course_ids = [course_id] + [
        str(item.get("course_id") or "")
        for item in alternative_courses
        if item.get("course_id") and str(item.get("course_id")) != course_id
    ]
    course_ids = [item for item in course_ids if item][:3]

    actions: list[dict[str, Any]] = [
        {
            "type": "create_training_plan",
            "employee_id": employee_id,
            "course_ids": course_ids,
            "skill_gaps": skill_gaps,
            "reason": rationale,
        },
        {
            "type": "create_training_enrollment",
            "employee_id": employee_id,
            "course_id": course_id,
            "reason": rationale,
        },
        {
            "type": "update_training_status",
            "employee_id": employee_id,
            "course_id": course_id,
            "status": "enrolled",
        },
        {
            "type": "notify_employee",
            "employee_id": employee_id,
            "message": (
                f"You have been enrolled in {primary_course.get('title')} "
                f"({course_id}). {rationale}"
            ),
        },
    ]
    if include_manager_notify and manager_id:
        actions.append(
            {
                "type": "notify_employee",
                "employee_id": manager_id,
                "message": (
                    f"Training enrollment for employee {employee_id}: "
                    f"{primary_course.get('title')} ({course_id})."
                ),
            }
        )
    return actions


def training_decision_agent(state: WorkflowState) -> dict[str, Any]:
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
    primary = dict(analysis.get("recommended_course") or {})
    alternatives = list(analysis.get("alternative_courses") or [])
    skill_gap_names = [
        str(item.get("skill") or item)
        for item in (analysis.get("skill_gaps") or [])
    ]
    patches: list[dict[str, Any]] = []

    _, notes_patch = search_short_term(state, agent="training_decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(
        state,
        agent="training_decision",
        employee_id=employee_id or None,
        workflow_type="training",
    )
    patches.append(history_patch)

    blockers = list(analysis.get("blockers") or policy.get("violations") or [])
    warnings = list(analysis.get("warnings") or policy.get("warnings") or [])
    evidence = [
        f"severity={policy.get('severity')}",
        f"gap_count={analysis.get('gap_count')}",
        f"primary_course={primary.get('course_id')}",
        f"alternatives={[item.get('course_id') for item in alternatives]}",
        f"skill_gaps={skill_gap_names}",
    ]
    if history:
        warnings.append("Prior training outcomes were available as context only.")

    pending_actions: list[dict[str, Any]] = []
    severity = str(policy.get("severity") or analysis.get("recommendation") or "blocked")

    if severity == "blocked" or not employee_id or not primary:
        outcome = "blocked"
        executable = False
        requires_human_approval = False
        confidence = 0.95
        rationale = (
            "Training recommendation is blocked due to eligibility, prerequisites, "
            "inactive course, or missing data: "
            + ("; ".join(str(item) for item in blockers) if blockers else "insufficient data.")
        )
    elif severity == "pending_approval" or policy.get("requires_human_approval"):
        outcome = "pending_approval"
        executable = False
        requires_human_approval = True
        confidence = 0.9
        rationale = (
            f"Recommended {primary.get('title')} ({primary.get('course_id')}) for {employee_id} "
            f"to address gaps {skill_gap_names}. "
            f"Course cost {primary.get('cost')} requires "
            f"{policy.get('approval_level') or 'manager'} approval before enrollment."
        )
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = [
            {
                "type": "request_human_approval",
                "employee_id": employee_id,
                "course_id": primary.get("course_id"),
                "approval_level": policy.get("approval_level"),
            }
        ]
    elif severity == "ready" and primary:
        outcome = "ready"
        executable = True
        requires_human_approval = False
        confidence = 0.9
        rationale = (
            f"Suitable training identified for {employee_id}: "
            f"{primary.get('title')} ({primary.get('course_id')}) covering "
            f"{primary.get('matched_skills') or skill_gap_names}. "
            "No approval required; enrollment and training plan can proceed."
        )
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = build_training_pending_actions(
            employee_id=employee_id,
            manager_id=manager_id,
            primary_course=primary,
            alternative_courses=alternatives,
            skill_gaps=skill_gap_names,
            rationale=rationale,
            include_manager_notify=True,
        )
    else:
        outcome = "recommend"
        executable = False
        requires_human_approval = False
        confidence = 0.86
        rationale = (
            f"Training recommendations for {employee_id}: "
            f"primary={primary.get('course_id') or 'none'}; "
            f"alternatives={[item.get('course_id') for item in alternatives]}. "
            "No automated enrollment scheduled."
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
            "course_id": primary.get("course_id"),
            "course_ids": [primary.get("course_id")]
            + [item.get("course_id") for item in alternatives],
            "skill_gaps": skill_gap_names,
            "approval_level": policy.get("approval_level"),
            "severity": severity,
        },
        evidence=evidence,
        blockers=blockers,
        warnings=warnings,
        influenced_by=[item.memory_id for item in history],
    )

    metadata = dict(state.get("metadata") or {})
    metadata["training_severity"] = severity
    metadata["training_recommendation"] = outcome
    metadata["recommended_course_id"] = primary.get("course_id")
    metadata["recommended_course"] = primary
    metadata["alternative_courses"] = alternatives
    metadata["skill_gaps"] = skill_gap_names

    _, memory_patch = append_short_term(
        state,
        agent="training_decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; executable={decision.executable}; "
            f"approval={decision.requires_human_approval}; course={primary.get('course_id')}."
        ),
        influenced_decision=bool(history or warnings),
    )
    patches.append(memory_patch)

    return node_update(
        "training_decision",
        f"Decision={decision.outcome}; course={primary.get('course_id')}; executable={decision.executable}.",
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        metadata=metadata,
        **combine_patches(*patches),
    )
