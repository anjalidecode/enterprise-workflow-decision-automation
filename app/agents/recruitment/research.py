"""Candidate Research Agent: retrieve candidates via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def candidate_research_agent(state: WorkflowState) -> dict[str, Any]:
    job = (state.get("retrieved_data") or {}).get("job") or {}
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    candidates: list[dict[str, Any]] = []

    if not job:
        errors.append("Candidate research skipped because no job was loaded.")
    else:
        result, patch = invoke_tool(
            state,
            agent="candidate_research",
            name="search_candidates",
            payload={
                "required_skills": list(job.get("required_skills") or []),
                "application_status": "active",
            },
        )
        patches.append(patch)
        if result.success:
            candidates = list((result.data or {}).get("candidates") or [])
        else:
            errors.append(result.error_message or "search_candidates failed.")

    retrieved = dict(state.get("retrieved_data") or {})
    retrieved["candidates"] = candidates
    retrieved["candidate_count"] = len(candidates)
    entities = merge_entities(
        state,
        candidate_ids=[item.get("candidate_id") for item in candidates],
    )

    _, memory_patch = append_short_term(
        state,
        agent="candidate_research",
        content=f"Retrieved {len(candidates)} candidate profile(s) for job {job.get('job_id')}.",
    )
    patches.append(memory_patch)

    return node_update(
        "candidate_research",
        f"Retrieved {len(candidates)} candidate(s).",
        entities=entities,
        retrieved_data=retrieved,
        errors=errors,
        **combine_patches(*patches),
    )
