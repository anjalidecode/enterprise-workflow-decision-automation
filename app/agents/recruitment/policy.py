"""Recruitment Policy Agent: authoritative policy validation via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def recruitment_policy_agent(state: WorkflowState) -> dict[str, Any]:
    job = (state.get("retrieved_data") or {}).get("job") or {}
    candidates = {
        str(item.get("candidate_id")): item
        for item in (state.get("retrieved_data") or {}).get("candidates") or []
    }
    scores = list((state.get("analysis_results") or {}).get("candidate_scores") or [])
    patches: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    errors: list[str] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="recruitment_policy",
        query="recruitment approval procedure interview scheduling policy",
        workflow_type="recruitment",
    )
    patches.append(knowledge_patch)

    for score_result in scores:
        candidate_id = str(score_result.get("candidate_id") or "")
        candidate = candidates.get(candidate_id)
        if not candidate:
            errors.append(f"Missing candidate profile for scored id {candidate_id}.")
            continue
        result, patch = invoke_tool(
            state,
            agent="recruitment_policy",
            name="validate_recruitment_policy",
            payload={
                "job": job,
                "candidate": candidate,
                "score_result": score_result,
            },
        )
        patches.append(patch)
        if result.success and result.data:
            validations.append(result.data)
        else:
            errors.append(result.error_message or f"Policy validation failed for {candidate_id}.")

    all_violations = []
    all_warnings = []
    for item in validations:
        all_violations.extend(item.get("violations") or [])
        all_warnings.extend(item.get("warnings") or [])

    requires_human_approval = any(
        item.get("requires_human_approval") for item in validations
    ) or True  # recruitment policy defaults to approval before shortlist

    policy_results = {
        "policy_id": (validations[0].get("policy_id") if validations else "HR-RECRUIT-001"),
        "candidate_validations": validations,
        "violations": all_violations,
        "warnings": all_warnings,
        "eligible": any(item.get("eligible_for_shortlist") for item in validations),
        "requires_human_approval": requires_human_approval,
    }

    _, memory_patch = append_short_term(
        state,
        agent="recruitment_policy",
        content=(
            f"Policy validation complete; eligible_shortlist="
            f"{sum(1 for item in validations if item.get('eligible_for_shortlist'))}; "
            f"violations={len(all_violations)}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "recruitment_policy",
        f"Applied recruitment policy to {len(validations)} candidate(s).",
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
