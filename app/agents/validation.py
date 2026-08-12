"""Validation Agent: verify the decision before any action is taken."""

from __future__ import annotations

from typing import Any

from app.agents.common import node_update
from app.orchestration.state import WorkflowState


def validation_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    analysis = state.get("analysis_results") or {}
    policy_results = state.get("policy_results") or {}
    issues: list[str] = []

    outcome = decision.get("outcome")
    if outcome not in {"approve", "reject", "pending_approval"}:
        issues.append("Decision outcome is missing or invalid.")

    if not decision.get("rationale"):
        issues.append("Decision is missing a rationale.")

    if outcome == "approve":
        if analysis.get("blockers"):
            issues.append("Approve decision conflicts with analysis blockers.")
        if not policy_results.get("eligible", False):
            issues.append("Approve decision conflicts with policy eligibility.")
        if not decision.get("executable"):
            issues.append("Approve decision is not marked executable.")

    if outcome == "pending_approval" and not state.get("requires_human_approval"):
        issues.append("Pending approval decision is missing the human-approval flag.")

    if outcome == "reject" and decision.get("executable"):
        issues.append("Reject decisions must not be executable.")

    passed = len(issues) == 0

    if not passed:
        route = "response"
        status = "validation_failed"
    elif state.get("requires_human_approval"):
        route = "response"
        status = "awaiting_human_approval"
    elif outcome == "approve" and decision.get("executable"):
        route = "action"
        status = "validated"
    else:
        route = "response"
        status = "validated"

    metadata = {
        **state.get("metadata", {}),
        "validation": {
            "passed": passed,
            "issues": issues,
            "route": route,
        },
        "route": route,
    }

    summary = (
        f"Validation {'passed' if passed else 'failed'}; "
        f"route={route}; issues={len(issues)}."
    )
    errors = [f"Validation: {item}" for item in issues]
    return node_update(
        "validation",
        summary,
        status=status,
        errors=errors,
        metadata=metadata,
    )
