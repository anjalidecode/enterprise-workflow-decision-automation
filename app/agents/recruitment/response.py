"""Recruitment Response Agent: summarize outcomes and persist compact LTM."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState


def recruitment_response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    job = (state.get("retrieved_data") or {}).get("job") or {}
    analysis = state.get("analysis_results") or {}
    shortlist = list(analysis.get("shortlist_candidates") or [])
    review = list(analysis.get("review_candidates") or [])
    rejected = list(analysis.get("rejected_candidates") or [])
    completed = list(state.get("completed_actions") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="recruitment_response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="recruitment_response",
        query="recruitment process interview procedure",
        workflow_type="recruitment",
    )
    patches.append(knowledge_patch)

    status = state.get("status") or "completed"
    if status == "awaiting_human_approval":
        final_status = "awaiting_human_approval"
    elif status == "validation_failed":
        final_status = "validation_failed"
    else:
        final_status = "completed"

    handbook = hits[0].title if hits else "Recruitment handbook"
    job_label = f"{job.get('title') or 'Unknown role'} ({job.get('job_id') or 'n/a'})"
    outcome = decision.get("outcome")

    if final_status == "awaiting_human_approval":
        response = (
            f"Recruitment recommendation for {job_label} requires human approval before "
            f"shortlist/interview actions. Recommended shortlist: {', '.join(shortlist) or 'none'}. "
            f"Review: {', '.join(review) or 'none'}. Rejected: {', '.join(rejected) or 'none'}. "
            f"Reason: {decision.get('rationale')}. Handbook: {handbook}."
        )
    elif outcome == "recommend":
        response = (
            f"No automatic shortlist for {job_label}. Candidates recommended for review: "
            f"{', '.join(review) or 'none'}. Rejected: {', '.join(rejected) or 'none'}. "
            f"Handbook: {handbook}."
        )
    elif outcome == "reject":
        response = (
            f"Recruitment for {job_label} produced no shortlist. "
            f"Rejected: {', '.join(rejected) or 'none'}. "
            f"Reason: {decision.get('rationale')}. Handbook: {handbook}."
        )
    else:
        shortlisted_actions = [
            item for item in completed if item.get("type") == "shortlist_candidate"
        ]
        interviews = [
            item for item in completed if item.get("type") == "schedule_interview"
        ]
        response = (
            f"Recruitment actions completed for {job_label}. "
            f"Shortlisted via tools: {len(shortlisted_actions)}; "
            f"interviews scheduled via tools: {len(interviews)}. "
            f"Handbook: {handbook}."
        )

    # Compact long-term outcome (no resumes / raw profiles).
    try:
        _, ltm_patch = write_long_term(
            state,
            agent="recruitment_response",
            payload={
                "employee_id": str(job.get("job_id") or "JOB"),
                "job_id": job.get("job_id"),
                "workflow_type": "recruitment",
                "outcome": outcome,
                "rationale_summary": str(decision.get("rationale") or "")[:400],
                "requires_human_approval": bool(state.get("requires_human_approval")),
                "shortlisted_count": len(shortlist),
            },
        )
        patches.append(ltm_patch)
    except Exception:
        # Safety rejection should not crash response composition.
        pass

    return node_update(
        "recruitment_response",
        f"Composed recruitment response; status={final_status}; notes={len(notes)}.",
        final_response=response,
        status=final_status,
        **combine_patches(*patches),
    )
