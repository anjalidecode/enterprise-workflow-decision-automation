"""Shared helpers for agent node updates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.orchestration.state import AgentOutput, WorkflowState


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_output(agent: str, summary: str) -> AgentOutput:
    return AgentOutput(agent=agent, summary=summary, timestamp=utc_now())


def node_update(agent: str, summary: str, **fields: Any) -> dict[str, Any]:
    """Return a LangGraph state patch including the standard trace fields."""

    return {
        "current_stage": agent,
        "completed_tasks": [agent],
        "agent_outputs": [record_output(agent, summary)],
        **fields,
    }


def leave_request_from_state(state: WorkflowState) -> dict[str, Any]:
    return dict(state.get("metadata", {}).get("leave_request", {}))


def combine_patches(*patches: dict[str, Any]) -> dict[str, Any]:
    """Merge tool and memory patches from multiple calls in one node."""

    merged: dict[str, Any] = {}
    tool_executions: list[dict[str, Any]] = []
    memory_accesses: list[dict[str, Any]] = []
    for patch in patches:
        tool_executions.extend(patch.get("tool_executions") or [])
        memory_accesses.extend(patch.get("memory_accesses") or [])
    if tool_executions:
        merged["tool_executions"] = tool_executions
    if memory_accesses:
        merged["memory_accesses"] = memory_accesses
    return merged
