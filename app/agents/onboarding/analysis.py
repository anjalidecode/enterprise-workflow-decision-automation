"""Onboarding Analysis Agent: combine employee, document, and policy findings."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState


def onboarding_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    employee = state.get("employee_data") or {}
    verification = (state.get("retrieved_data") or {}).get("document_verification") or {}
    policy = state.get("policy_results") or {}
    patches: list[dict[str, Any]] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="onboarding_analysis",
        query="document verification HR orientation manager responsibilities",
        workflow_type="onboarding",
    )
    patches.append(knowledge_patch)

    blockers = list(policy.get("violations") or [])
    warnings = list(policy.get("warnings") or [])
    missing = list(verification.get("missing_documents") or [])
    invalid = list(verification.get("invalid_documents") or [])

    if missing:
        blockers.append("Missing documents: " + ", ".join(str(item) for item in missing))
    if invalid:
        blockers.append("Invalid documents: " + ", ".join(str(item) for item in invalid))

    privileged = list(policy.get("privileged_access_required") or [])
    if privileged:
        warnings.append("Privileged access requires approval: " + ", ".join(privileged))

    if blockers:
        recommendation = "blocked"
    elif policy.get("requires_human_approval") or privileged:
        recommendation = "pending_approval"
    elif policy.get("eligible"):
        recommendation = "ready"
    else:
        recommendation = "blocked"

    analysis_results = {
        "recommendation": recommendation,
        "employee_id": employee.get("employee_id"),
        "role": employee.get("role"),
        "department": employee.get("department"),
        "joining_date": employee.get("joining_date"),
        "missing_documents": missing,
        "invalid_documents": invalid,
        "verified_documents": list(verification.get("verified_documents") or []),
        "mandatory_tasks": list(policy.get("mandatory_tasks") or []),
        "equipment_required": list(policy.get("equipment_required") or []),
        "access_required": list(policy.get("access_required") or []),
        "privileged_access_required": privileged,
        "blockers": blockers,
        "warnings": warnings,
        "policy_eligible": bool(policy.get("eligible")),
    }

    _, memory_patch = append_short_term(
        state,
        agent="onboarding_analysis",
        content=(
            f"Analysis recommendation={recommendation}; blockers={len(blockers)}; "
            f"warnings={len(warnings)}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "onboarding_analysis",
        f"Onboarding analysis recommendation={recommendation}.",
        analysis_results=analysis_results,
        **combine_patches(*patches),
    )
