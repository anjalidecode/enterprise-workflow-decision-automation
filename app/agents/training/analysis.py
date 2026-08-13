"""Training Analysis: combine gaps, courses, eligibility, and warnings."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState


def training_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    employee = state.get("employee_data") or {}
    policy = state.get("policy_results") or {}
    existing = state.get("analysis_results") or {}
    request = (state.get("metadata") or {}).get("training_request") or {}
    patches: list[dict[str, Any]] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="training_analysis",
        query="course selection development planning prerequisites",
        workflow_type="training",
    )
    patches.append(knowledge_patch)

    employee_id = str(
        employee.get("employee_id")
        or existing.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    skill_gaps = list(existing.get("skill_gaps") or retrieved.get("skill_gaps") or [])
    primary = dict(retrieved.get("recommended_course") or {})
    alternatives = list(retrieved.get("alternative_courses") or [])
    matched = list(retrieved.get("matched_courses") or [])

    blockers = list(policy.get("violations") or [])
    warnings = list(policy.get("warnings") or [])
    if employee_id and not skill_gaps and not matched:
        blockers.append("No skill gaps or matching courses identified.")
    if employee_id and skill_gaps and not primary:
        blockers.append("Skill gaps identified but no suitable active course matched.")

    reasons: list[str] = []
    if primary:
        covered = primary.get("matched_skills") or []
        reasons.append(
            f"{primary.get('course_id')} selected because it covers "
            f"{', '.join(str(item) for item in covered) or 'prioritized skill gaps'} "
            f"(level={primary.get('level')}, cost={primary.get('cost')}, "
            f"format={primary.get('format')})."
        )
    for alt in alternatives:
        reasons.append(
            f"Alternative {alt.get('course_id')}: covers "
            f"{', '.join(str(item) for item in (alt.get('matched_skills') or [])) or 'related skills'}."
        )

    recommendation = "pending_decision"
    severity = str(policy.get("severity") or "")
    if severity == "blocked" or blockers:
        recommendation = "blocked"
    elif policy.get("requires_human_approval") or severity == "pending_approval":
        recommendation = "pending_approval"
    elif primary and severity == "ready":
        recommendation = "ready"
    elif primary:
        recommendation = "recommend"
    else:
        recommendation = "blocked"

    analysis = {
        **existing,
        "employee_id": employee_id or None,
        "department": employee.get("department"),
        "manager": employee.get("manager"),
        "operation": request.get("operation"),
        "skill_gaps": skill_gaps,
        "gap_count": len(skill_gaps),
        "prioritized_skills": list(existing.get("prioritized_skills") or retrieved.get("prioritized_skills") or []),
        "recommended_course": primary or None,
        "alternative_courses": alternatives,
        "matched_courses": matched,
        "recommendation_reasons": reasons,
        "recommendation": recommendation,
        "blockers": blockers,
        "warnings": warnings,
        "policy_severity": severity,
        "approval_level": policy.get("approval_level"),
    }

    _, memory_patch = append_short_term(
        state,
        agent="training_analysis",
        content=(
            f"Training analysis employee={employee_id or 'unknown'}; "
            f"gaps={len(skill_gaps)}; primary={primary.get('course_id') if primary else None}; "
            f"recommendation={recommendation}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "training_analysis",
        (
            f"Analyzed training options; recommendation={recommendation}; "
            f"gaps={len(skill_gaps)}; courses={len(matched)}."
        ),
        analysis_results=analysis,
        **combine_patches(*patches),
    )
