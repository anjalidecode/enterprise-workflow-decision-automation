"""Action Agent: execute approved write tools through the tool layer."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def action_agent(state: WorkflowState) -> dict[str, Any]:
    validation = (state.get("metadata") or {}).get("validation") or {}
    decision = state.get("decision") or {}
    if (
        not validation.get("passed")
        or state.get("requires_human_approval")
        or not decision.get("executable")
    ):
        return node_update(
            "action",
            "Skipped write tools because the decision is not validated and executable.",
            errors=["Action Agent refused to execute unvalidated or non-executable actions."],
        )

    pending = list(state.get("pending_actions") or [])
    employee = dict(state.get("employee_data") or {})
    completed: list[dict[str, Any]] = []
    errors: list[str] = []
    patches: list[dict[str, Any]] = []

    for action in pending:
        action_type = str(action.get("type") or "")
        payload = {
            **action,
            "workflow_id": state.get("workflow_id"),
        }
        result, patch = invoke_tool(
            state,
            agent="action",
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
            if action_type == "update_leave_balance" and result.data:
                balances = dict(employee.get("leave_balances") or {})
                leave_type = result.data.get("leave_type", "annual")
                balances[leave_type] = result.data.get("new_balance")
                employee["leave_balances"] = balances
        else:
            errors.append(result.error_message or f"{action_type} failed.")
            if action_type == "update_leave_balance":
                break

    _, memory_patch = append_short_term(
        state,
        agent="action",
        content=f"Action executed {len(completed)} write tool(s).",
    )
    patches.append(memory_patch)

    summary = f"Executed {len(completed)} write tool(s) via the tool layer."
    return node_update(
        "action",
        summary,
        employee_data=employee,
        completed_actions=completed,
        pending_actions=[],
        status="actions_executed",
        errors=errors,
        **combine_patches(*patches),
    )
