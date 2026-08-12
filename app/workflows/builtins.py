"""Builtin workflow registrations for the platform spine.

Phase 4A registers only Leave & Attendance. Additional workflows plug in later
without changing Registry/Router/Engine design.
"""

from __future__ import annotations

from typing import Any

from app.workflows.contracts import WorkflowSpec
from app.workflows.leave_workflow import (
    AGENT_NODES,
    build_leave_workflow,
    run_leave_workflow,
)
from app.workflows.registry import WorkflowRegistry

LEAVE_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="leave_attendance",
    name="Leave & Attendance",
    description=(
        "Evaluate leave requests against employee records, leave balances, and "
        "structured leave policy. Supports approve, reject, and human approval paths."
    ),
    supported_request_hints=[
        "leave",
        "time off",
        "pto",
        "vacation",
        "annual leave",
        "sick leave",
        "attendance",
    ],
    required_agents=list(AGENT_NODES),
    required_tool_capabilities=[
        "employee.lookup",
        "employee.leave_balance",
        "policy.lookup",
        "policy.validate_leave",
        "leave.impact",
        "leave.balance.update",
        "notification.send",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "leave_attendance",
    },
    entry_node="orchestrator",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)


def _leave_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "leave_attendance",
    **_: Any,
):
    """Adapter around the existing leave runner. Does not rewrite the graph."""

    return run_leave_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def register_builtin_workflows(registry: WorkflowRegistry) -> None:
    """Register Phase 4A builtins (leave only)."""

    registry.register(
        LEAVE_WORKFLOW_SPEC,
        runner=_leave_runner,
        graph_factory=build_leave_workflow,
        validate_tools=True,
    )
