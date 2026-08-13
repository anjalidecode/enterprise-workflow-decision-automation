"""Training catalog research: match courses to skill gaps via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def training_catalog_research_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    analysis = state.get("analysis_results") or {}
    gaps = list(analysis.get("skill_gaps") or retrieved.get("skill_gaps") or [])
    history = list(retrieved.get("training_history") or [])
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    matched_courses: list[dict[str, Any]] = []
    course_details: list[dict[str, Any]] = []

    completed_or_active = {
        str(item.get("course_id") or "").upper()
        for item in history
        if str(item.get("status") or "").lower() in {"completed", "in_progress", "enrolled"}
    }

    # Search catalog per prioritized skill (tools only for catalog access).
    prioritized = list(analysis.get("prioritized_skills") or [item.get("skill") for item in gaps])
    seen_ids: set[str] = set()
    for skill in prioritized:
        if not skill:
            continue
        result, patch = invoke_tool(
            state,
            agent="training_catalog_research",
            name="search_training_catalog",
            payload={"skill": str(skill)},
        )
        patches.append(patch)
        if not result.success:
            errors.append(result.error_message or f"catalog search failed for {skill}")
            continue
        for course in result.data.get("courses") or []:
            course_id = str(course.get("course_id") or "").upper()
            if not course_id or course_id in seen_ids:
                continue
            if course_id in completed_or_active:
                continue
            seen_ids.add(course_id)
            course_skills = [str(s).lower() for s in (course.get("skills") or [])]
            covered = [
                str(item.get("skill"))
                for item in gaps
                if str(item.get("skill") or "").lower() in course_skills
            ]
            matched_courses.append(
                {
                    **course,
                    "matched_skills": covered,
                    "match_score": len(covered),
                }
            )

    # Deterministic ranking: more gap coverage, then lower cost.
    matched_courses.sort(
        key=lambda row: (
            -int(row.get("match_score") or 0),
            float(row.get("cost") or 0),
            str(row.get("course_id") or ""),
        )
    )
    # Prefer active courses with seats.
    matched_courses = [
        item
        for item in matched_courses
        if str(item.get("status") or "").lower() == "active"
        and int(item.get("seats_available") or 0) > 0
    ]

    # Enrich top matches with course.get tool.
    for course in matched_courses[:5]:
        course_id = str(course.get("course_id") or "")
        detail_result, detail_patch = invoke_tool(
            state,
            agent="training_catalog_research",
            name="get_training_course",
            payload={"course_id": course_id},
        )
        patches.append(detail_patch)
        if detail_result.success and detail_result.data:
            course_details.append(
                {
                    **dict(detail_result.data),
                    "matched_skills": course.get("matched_skills") or [],
                    "match_score": course.get("match_score") or 0,
                }
            )
        else:
            course_details.append(course)

    primary = course_details[0] if course_details else None
    alternatives = course_details[1:3] if len(course_details) > 1 else []

    retrieved = {
        **retrieved,
        "matched_courses": course_details,
        "recommended_course": primary,
        "alternative_courses": alternatives,
        "catalog_match_count": len(course_details),
    }

    _, memory_patch = append_short_term(
        state,
        agent="training_catalog_research",
        content=(
            f"Matched {len(course_details)} course(s); "
            f"primary={primary.get('course_id') if primary else None}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "training_catalog_research",
        (
            f"Catalog research found {len(course_details)} matching course(s); "
            f"primary={primary.get('course_id') if primary else 'none'}."
        ),
        retrieved_data=retrieved,
        errors=errors,
        **combine_patches(*patches),
    )
