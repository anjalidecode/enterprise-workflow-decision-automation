"""Skill gap analysis via training.skill_gap.calculate tool."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def skill_gap_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    employee = state.get("employee_data") or {}
    request = (state.get("metadata") or {}).get("training_request") or {}
    employee_id = str(
        employee.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    performance_context = {
        "skill_gaps": list(retrieved.get("performance_skill_gaps") or []),
    }
    result, patch = invoke_tool(
        state,
        agent="skill_gap_analysis",
        name="calculate_skill_gap",
        payload={
            "employee_id": employee_id,
            "employee_skills": list(retrieved.get("employee_skills") or []),
            "role_requirements": list(retrieved.get("role_requirements") or []),
            "performance_context": performance_context,
        },
    )
    patches.append(patch)

    gaps: list[dict[str, Any]] = []
    gap_summary: dict[str, Any] = {}
    if result.success and result.data:
        gap_summary = dict(result.data)
        gaps = list(result.data.get("skill_gaps") or [])
    else:
        errors.append(result.error_message or "calculate_skill_gap failed.")

    retrieved = {
        **retrieved,
        "skill_gaps": gaps,
        "skill_gap_summary": gap_summary,
        "prioritized_skills": list(gap_summary.get("prioritized_skills") or []),
    }

    _, memory_patch = append_short_term(
        state,
        agent="skill_gap_analysis",
        content=(
            f"Skill gaps for {employee_id or 'unknown'}: "
            f"{[item.get('skill') for item in gaps]}."
        ),
    )
    patches.append(memory_patch)

    analysis = {
        **(state.get("analysis_results") or {}),
        "employee_id": employee_id or None,
        "skill_gaps": gaps,
        "prioritized_skills": list(gap_summary.get("prioritized_skills") or []),
        "gap_count": len(gaps),
    }

    return node_update(
        "skill_gap_analysis",
        f"Identified {len(gaps)} skill gap(s) for {employee_id or 'unknown'}.",
        retrieved_data=retrieved,
        analysis_results=analysis,
        errors=errors,
        **combine_patches(*patches),
    )
