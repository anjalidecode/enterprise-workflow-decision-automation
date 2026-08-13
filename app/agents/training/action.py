"""Training Action Agent: plan, enrollment, status, notifications via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool

WRITE_TOOLS = {
    "create_training_plan",
    "create_training_enrollment",
    "update_training_status",
    "notify_employee",
}


def training_action_agent(state: WorkflowState) -> dict[str, Any]:
    validation = (state.get("metadata") or {}).get("validation") or {}
    decision = state.get("decision") or {}
    if (
        not validation.get("passed")
        or state.get("requires_human_approval")
        or not decision.get("executable")
    ):
        return node_update(
            "training_action",
            "Skipped training writes because the decision is not validated and executable.",
            errors=["Training Action refused unvalidated or non-executable actions."],
        )

    pending = list(state.get("pending_actions") or [])
    completed: list[dict[str, Any]] = []
    errors: list[str] = []
    patches: list[dict[str, Any]] = []

    for action in pending:
        action_type = str(action.get("type") or "")
        if action_type == "request_human_approval":
            continue
        payload = {
            **{key: value for key, value in action.items() if key != "type"},
            "workflow_id": state.get("workflow_id"),
        }
        result, patch = invoke_tool(
            state,
            agent="training_action",
            name=action_type,
            payload=payload,
            validated=True,
        )
        patches.append(patch)
        if result.success:
            completed.append(
                {
                    "type": action_type,
                    "success": True,
                    "source": result.source,
                    **(result.data or {}),
                }
            )
        else:
            errors.append(result.error_message or f"{action_type} failed.")
            if action_type in WRITE_TOOLS:
                break

    _, memory_patch = append_short_term(
        state,
        agent="training_action",
        content=f"Training action executed {len(completed)} write tool(s).",
    )
    patches.append(memory_patch)

    return node_update(
        "training_action",
        f"Executed {len(completed)} training write tool(s).",
        completed_actions=completed,
        pending_actions=[],
        status="actions_executed",
        errors=errors,
        **combine_patches(*patches),
    )
