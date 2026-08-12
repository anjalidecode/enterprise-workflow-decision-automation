"""Candidate Analysis Agent: compare profiles to job requirements."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState


def _analyze_one(job: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    required = {str(s).lower() for s in (job.get("required_skills") or [])}
    preferred = {str(s).lower() for s in (job.get("preferred_skills") or [])}
    skills = {str(s).lower() for s in (candidate.get("skills") or [])}
    matched_required = sorted(required & skills)
    missing_required = sorted(required - skills)
    matched_preferred = sorted(preferred & skills)
    min_exp = int(job.get("minimum_experience") or 0)
    years = int(candidate.get("experience_years") or 0)
    experience_match = years >= min_exp
    education_match = str(candidate.get("education") or "").lower() == str(
        job.get("education") or ""
    ).lower() or str(candidate.get("education") or "").lower() in {
        "master",
        "phd",
    }
    location_match = str(job.get("location") or "").lower() in {
        str(candidate.get("location") or "").lower(),
        str(candidate.get("preferred_location") or "").lower(),
        "remote",
    } or str(candidate.get("preferred_location") or "").lower() == "remote"

    strengths: list[str] = []
    concerns: list[str] = []
    if matched_required:
        strengths.append("Matches required skills: " + ", ".join(matched_required))
    if matched_preferred:
        strengths.append("Matches preferred skills: " + ", ".join(matched_preferred))
    if experience_match:
        strengths.append(f"Meets experience requirement ({years}y).")
    else:
        concerns.append(f"Below minimum experience ({years}y < {min_exp}y).")
    if missing_required:
        concerns.append("Missing required skills: " + ", ".join(missing_required))
    if not education_match:
        concerns.append("Education may not fully match the job requirement.")
    if not location_match:
        concerns.append("Location alignment is weak.")

    return {
        "candidate_id": candidate.get("candidate_id"),
        "name": candidate.get("name"),
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "experience_match": experience_match,
        "education_match": education_match,
        "location_match": location_match,
        "strengths": strengths,
        "concerns": concerns,
    }


def candidate_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    job = (state.get("retrieved_data") or {}).get("job") or {}
    candidates = list((state.get("retrieved_data") or {}).get("candidates") or [])
    analyses = [_analyze_one(job, candidate) for candidate in candidates]

    patches: list[dict[str, Any]] = []
    _, knowledge_patch = search_knowledge(
        state,
        agent="candidate_analysis",
        query="candidate evaluation guidelines required skills",
        workflow_type="recruitment",
    )
    patches.append(knowledge_patch)

    analysis_results = dict(state.get("analysis_results") or {})
    analysis_results["candidate_analyses"] = analyses

    _, memory_patch = append_short_term(
        state,
        agent="candidate_analysis",
        content=f"Analyzed {len(analyses)} candidate profile(s) against job requirements.",
    )
    patches.append(memory_patch)

    return node_update(
        "candidate_analysis",
        f"Analyzed {len(analyses)} candidate(s).",
        analysis_results=analysis_results,
        **combine_patches(*patches),
    )
