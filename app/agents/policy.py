"""Policy Agent: retrieve and evaluate leave policy through the tool layer."""

from __future__ import annotations

from typing import Any

from app.agents.common import leave_request_from_state, node_update
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool, merge_tool_patches


def policy_agent(state: WorkflowState) -> dict[str, Any]:
    leave_request = leave_request_from_state(state)
    errors: list[str] = []

    policy_result, policy_patch = invoke_tool(
        state,
        agent="policy",
        capability="policy.lookup",
        payload={},
    )
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
        }
        summary = "Policy evaluation failed."
    else:
        policy_results = dict(validation_result.data or {})
        if policy_result.success and policy_result.data:
            policy_results.setdefault("policy_id", policy_result.data.get("policy_id"))
            policy_results.setdefault("title", policy_result.data.get("title"))
        summary = (
            f"Applied {policy_results.get('policy_id')}: "
            f"{len(policy_results.get('violations') or [])} violation(s), "
            f"{len(policy_results.get('warnings') or [])} warning(s)."
        )

    return node_update(
        "policy",
        summary,
        policy_results=policy_results,
        errors=errors,
        **merge_tool_patches(policy_patch, validation_patch),
    )
