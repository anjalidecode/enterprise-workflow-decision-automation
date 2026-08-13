"""Performance Analysis: strengths, concerns, skill gaps, and development needs."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState


def performance_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    employee = state.get("employee_data") or {}
    request = (state.get("metadata") or {}).get("performance_request") or {}
    existing = state.get("analysis_results") or {}
    summary = dict(retrieved.get("performance_summary") or existing.get("summary") or {})
    employee_id = str(
        employee.get("employee_id")
        or existing.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    review_period = str(
        retrieved.get("review_period") or existing.get("review_period") or "2026-Q2"
    )
    support_findings = list(retrieved.get("support_findings") or [])
    scan = bool(retrieved.get("performance_scan")) and not employee_id
    kpis = dict(summary.get("kpis") or {})
    patches: list[dict[str, Any]] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="performance_analysis",
        query="performance review goal setting KPI evaluation employee development",
        workflow_type="performance",
    )
    patches.append(knowledge_patch)

    strengths = list(summary.get("strengths") or [])
    improvement_areas = list(summary.get("improvement_areas") or [])
    skill_gaps = list(summary.get("skill_gaps") or [])
    projects = list(summary.get("projects") or [])
    achievement = summary.get("goal_achievement_pct")
    blockers = list(existing.get("blockers") or [])
    if employee_id and not retrieved.get("performance_records") and not summary:
        blockers.append("No performance records available for analysis.")

    if scan:
        recommendation = "scan_report"
    elif not employee_id:
        recommendation = "blocked"
    elif not retrieved.get("performance_records") or not retrieved.get("performance_goals"):
        recommendation = "blocked"
        if "No performance records available for analysis." not in blockers:
            blockers.append("Missing performance records or goals for the requested period.")
    else:
        recommendation = "pending_policy"

    analysis = {
        **existing,
        "employee_id": employee_id or None,
        "department": employee.get("department"),
        "manager": employee.get("manager"),
        "review_period": review_period,
        "summary": summary,
        "kpis": kpis,
        "projects": projects,
        "strengths": strengths,
        "improvement_areas": improvement_areas,
        "skill_gaps": skill_gaps,
        "goal_achievement_pct": achievement,
        "completed_goals": list(summary.get("completed_goals") or existing.get("completed_goals") or []),
        "partial_goals": list(summary.get("partial_goals") or existing.get("partial_goals") or []),
        "unmet_goals": list(summary.get("unmet_goals") or existing.get("unmet_goals") or []),
        "support_findings": support_findings,
        "scan_mode": scan,
        "attendance_signals_considered": False,
        "recommendation": recommendation,
        "blockers": blockers,
        "warnings": list(existing.get("warnings") or []),
        "development_recommendations": skill_gaps or improvement_areas,
    }

    _, memory_patch = append_short_term(
        state,
        agent="performance_analysis",
        content=(
            f"Performance analysis employee={employee_id or 'scan'}; "
            f"achievement={achievement}; strengths={len(strengths)}; "
            f"skill_gaps={skill_gaps}; concerns={improvement_areas}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "performance_analysis",
        (
            f"Analyzed performance; achievement={achievement if achievement is not None else 'n/a'}%; "
            f"strengths={len(strengths)}; skill_gaps={len(skill_gaps)}."
        ),
        analysis_results=analysis,
        **combine_patches(*patches),
    )
