"""Candidate Scoring Agent: deterministic weighted scores via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def candidate_scoring_agent(state: WorkflowState) -> dict[str, Any]:
    job = (state.get("retrieved_data") or {}).get("job") or {}
    candidates = list((state.get("retrieved_data") or {}).get("candidates") or [])
    scores: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    for candidate in candidates:
        result, patch = invoke_tool(
            state,
            agent="candidate_scoring",
            name="calculate_candidate_score",
            payload={"job": job, "candidate": candidate},
        )
        patches.append(patch)
        if result.success and result.data:
            scores.append(result.data)
        else:
            errors.append(
                result.error_message
                or f"Scoring failed for {candidate.get('candidate_id')}."
            )

    scores.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
    analysis_results = dict(state.get("analysis_results") or {})
    analysis_results["candidate_scores"] = scores

    _, memory_patch = append_short_term(
        state,
        agent="candidate_scoring",
        content=(
            f"Scored {len(scores)} candidate(s). "
            f"Top={scores[0].get('candidate_id') if scores else 'n/a'} "
            f"score={scores[0].get('score') if scores else 'n/a'}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "candidate_scoring",
        f"Calculated scores for {len(scores)} candidate(s).",
        analysis_results=analysis_results,
        errors=errors,
        **combine_patches(*patches),
    )
