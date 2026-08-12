"""Recruitment Decision Agent: classify candidates and set overall outcome."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, recall_long_term, search_short_term
from app.models.decision import WorkflowDecision
from app.orchestration.state import WorkflowState


def recruitment_decision_agent(state: WorkflowState) -> dict[str, Any]:
    job = (state.get("retrieved_data") or {}).get("job") or {}
    scores = {
        str(item.get("candidate_id")): item
        for item in (state.get("analysis_results") or {}).get("candidate_scores") or []
    }
    validations = list((state.get("policy_results") or {}).get("candidate_validations") or [])
    patches: list[dict[str, Any]] = []

    _, notes_patch = search_short_term(state, agent="recruitment_decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(
        state,
        agent="recruitment_decision",
        employee_id=str(job.get("job_id") or "") or None,
    )
    patches.append(history_patch)

    classifications: list[dict[str, Any]] = []
    shortlist: list[str] = []
    review: list[str] = []
    rejected: list[str] = []
    evidence: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    for item in validations:
        candidate_id = str(item.get("candidate_id") or "")
        score = float((scores.get(candidate_id) or {}).get("score") or 0)
        hint = item.get("classification_hint") or "reject"
        eligible = bool(item.get("eligible_for_shortlist"))
        if eligible and hint == "shortlist":
            label = "shortlist"
            shortlist.append(candidate_id)
        elif hint == "review" or (not eligible and score >= 60):
            label = "review"
            review.append(candidate_id)
        else:
            label = "reject"
            rejected.append(candidate_id)
        classifications.append(
            {
                "candidate_id": candidate_id,
                "label": label,
                "score": score,
                "eligible_for_shortlist": eligible,
                "violations": list(item.get("violations") or []),
                "warnings": list(item.get("warnings") or []),
            }
        )
        evidence.append(f"{candidate_id}:{label}:{score}")
        blockers.extend(item.get("violations") or [])
        warnings.extend(item.get("warnings") or [])

    # Cap shortlist size from policy defaults.
    max_shortlist = 3
    shortlist = shortlist[:max_shortlist]

    if not job:
        outcome = "reject"
        rationale = "No job requisition was available for recruitment decision."
        executable = False
        requires_human_approval = False
        pending_actions: list[dict[str, Any]] = []
        confidence = 0.95
    elif shortlist:
        outcome = "pending_approval"
        rationale = (
            "Candidates recommended for shortlist pending human approval: "
            + ", ".join(shortlist)
            + "."
        )
        if review:
            rationale += " Review also recommended for: " + ", ".join(review) + "."
        executable = False
        requires_human_approval = True
        pending_actions = [
            {
                "type": "request_human_approval",
                "job_id": job.get("job_id"),
                "candidate_ids": shortlist,
            }
        ]
        confidence = 0.82 if not warnings else 0.74
    elif review:
        outcome = "recommend"
        rationale = "No shortlist-ready candidates; recommend human review for: " + ", ".join(
            review
        )
        executable = False
        requires_human_approval = False
        pending_actions = []
        confidence = 0.8
    else:
        outcome = "reject"
        rationale = "No candidates met recruitment shortlist or review thresholds."
        executable = False
        requires_human_approval = False
        pending_actions = []
        confidence = 0.9

    if history:
        warnings.append("Prior recruitment outcomes were available as context only.")

    decision = WorkflowDecision(
        outcome=outcome,  # type: ignore[arg-type]
        rationale=rationale,
        executable=executable,
        confidence=confidence,
        requires_human_approval=requires_human_approval,
        entity_refs={
            "job_id": job.get("job_id"),
            "shortlist": shortlist,
            "review": review,
            "rejected": rejected,
        },
        evidence=evidence,
        blockers=blockers,
        warnings=warnings,
        influenced_by=[item.memory_id for item in history],
    )

    analysis_results = dict(state.get("analysis_results") or {})
    analysis_results["candidate_classifications"] = classifications
    analysis_results["shortlist_candidates"] = shortlist
    analysis_results["review_candidates"] = review
    analysis_results["rejected_candidates"] = rejected
    # Policy eligibility for validation agent (leave-compatible shape).
    policy_results = dict(state.get("policy_results") or {})
    policy_results["eligible"] = bool(shortlist)

    metadata = dict(state.get("metadata") or {})
    metadata["shortlist_candidates"] = shortlist
    metadata["review_candidates"] = review
    metadata["rejected_candidates"] = rejected

    _, memory_patch = append_short_term(
        state,
        agent="recruitment_decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; shortlist={shortlist}; "
            f"review={review}; rejected={rejected}."
        ),
        influenced_decision=bool(history or warnings),
    )
    patches.append(memory_patch)

    return node_update(
        "recruitment_decision",
        f"Decision={decision.outcome}; shortlist={len(shortlist)}; review={len(review)}.",
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        analysis_results=analysis_results,
        policy_results=policy_results,
        metadata=metadata,
        **combine_patches(*patches),
    )
