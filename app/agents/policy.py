"""Policy Agent: evaluate structured policy and retrieve handbook context."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, leave_request_from_state, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def policy_agent(state: WorkflowState) -> dict[str, Any]:
    leave_request = leave_request_from_state(state)
    errors: list[str] = []
    patches: list[dict[str, Any]] = []

    policy_result, policy_patch = invoke_tool(
        state,
        agent="policy",
        capability="policy.lookup",
        payload={},
    )
    patches.append(policy_patch)
    validation_result, validation_patch = invoke_tool(
        state,
        agent="policy",
        capability="policy.validate_leave",
        payload={
            "employee_id": leave_request.get("employee_id"),
            "days": leave_request.get("days"),
            "leave_type": leave_request.get("leave_type", "annual"),
            "start_date": leave_request.get("start_date"),
        },
    )
    patches.append(validation_patch)

    days = leave_request.get("days")
    query = (
        "manager approval for long leave"
        if isinstance(days, int) and days >= 5
        else "leave request guidance"
    )
    hits, knowledge_patch = search_knowledge(state, agent="policy", query=query)
    patches.append(knowledge_patch)

    if not policy_result.success:
        errors.append(policy_result.error_message or "Leave policy lookup failed.")
    if not validation_result.success:
        errors.append(validation_result.error_message or "Leave policy validation failed.")
        policy_results: dict[str, Any] = {
            "policy_id": None,
            "violations": errors,
            "warnings": [],
            "requires_human_approval": False,
            "eligible": False,
            "knowledge_citations": [hit.title for hit in hits],
        }
        summary = "Policy evaluation failed."
        note = "Policy validation failed."
    else:
        policy_results = dict(validation_result.data or {})
        if policy_result.success and policy_result.data:
            policy_results.setdefault("policy_id", policy_result.data.get("policy_id"))
            policy_results.setdefault("title", policy_result.data.get("title"))
        policy_results["knowledge_citations"] = [hit.title for hit in hits]
        summary = (
            f"Applied {policy_results.get('policy_id')}: "
            f"{len(policy_results.get('violations') or [])} violation(s), "
            f"{len(policy_results.get('warnings') or [])} warning(s)."
        )
        note = (
            f"Policy validation found {len(policy_results.get('violations') or [])} violation(s)."
        )

    _, note_patch = append_short_term(state, agent="policy", content=note)
    patches.append(note_patch)

    return node_update(
        "policy",
        summary,
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
