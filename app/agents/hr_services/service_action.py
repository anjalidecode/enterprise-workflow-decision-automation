"""Service Action: create tickets/documents, route to HR, notify via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool

WRITE_TOOLS = {
    "create_hr_service_request",
    "update_hr_service_request",
    "create_hr_document_request",
    "route_hr_service_to_hr",
    "notify_employee",
}


def service_action_agent(state: WorkflowState) -> dict[str, Any]:
    validation = (state.get("metadata") or {}).get("validation") or {}
    decision = state.get("decision") or {}
    if (
        not validation.get("passed")
        or state.get("requires_human_approval")
        or not decision.get("executable")
    ):
        return node_update(
            "service_action",
            "Skipped HR services writes because the decision is not validated and executable.",
            errors=["Service Action refused unvalidated or non-executable actions."],
        )

    pending = list(state.get("pending_actions") or [])
    completed: list[dict[str, Any]] = []
    errors: list[str] = []
    patches: list[dict[str, Any]] = []
    created_request_id = ""

    for action in pending:
        action_type = str(action.get("type") or "")
        if action_type == "request_human_approval":
            continue
        payload = {
            **{key: value for key, value in action.items() if key != "type"},
            "workflow_id": state.get("workflow_id"),
        }
        if action_type == "route_hr_service_to_hr" and payload.get("request_id") == "__from_create__":
            if not created_request_id:
                errors.append("route_hr_service_to_hr skipped: no created request_id.")
                continue
            payload["request_id"] = created_request_id

        result, patch = invoke_tool(
            state,
            agent="service_action",
            name=action_type,
            payload=payload,
            validated=True,
        )
        patches.append(patch)
        if result.success:
            data = dict(result.data or {})
            if action_type in {"create_hr_service_request", "create_hr_document_request"}:
                created_request_id = str(data.get("request_id") or created_request_id)
            completed.append(
                {
                    "type": action_type,
                    "success": True,
                    "source": result.source,
                    **data,
                }
            )
        else:
            errors.append(result.error_message or f"{action_type} failed.")
            if action_type in WRITE_TOOLS:
                break

    _, memory_patch = append_short_term(
        state,
        agent="service_action",
        content=f"HR services action executed {len(completed)} write tool(s).",
    )
    patches.append(memory_patch)

    metadata = {
        **(state.get("metadata") or {}),
        "created_request_id": created_request_id or None,
    }

    return node_update(
        "service_action",
        f"Executed {len(completed)} HR services write tool(s).",
        completed_actions=completed,
        pending_actions=[],
        status="actions_executed",
        errors=errors,
        metadata=metadata,
        **combine_patches(*patches),
    )
