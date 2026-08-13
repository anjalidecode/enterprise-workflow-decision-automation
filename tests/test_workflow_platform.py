"""Phase 4A tests: WorkflowSpec, Registry, Router, Engine, Result/Audit/Metrics."""

from __future__ import annotations

import pytest

from app.models.decision import WorkflowDecision
from app.models.leave import LeaveDecision
from app.workflows.builtins import LEAVE_WORKFLOW_SPEC
from app.workflows.contracts import (
    ApprovalDecision,
    WorkflowAuditSnapshot,
    WorkflowRunMetrics,
    WorkflowSpec,
)
from app.workflows.engine import WorkflowEngine, get_workflow_engine
from app.workflows.errors import UnknownWorkflowError, WorkflowResumeError
from app.workflows.registry import WorkflowRegistry, get_workflow_registry
from app.workflows.router import WorkflowRouter

LEAVE_APPROVE = "Check whether employee E001 can take 3 days of leave from 2026-08-17."
LEAVE_REJECT = "Check whether employee E002 can take 3 days of leave from 2026-08-17."
LEAVE_APPROVAL = "Check whether employee E001 can take 8 days of leave from 2026-08-17."


def test_workflow_spec_creation() -> None:
    spec = WorkflowSpec(
        workflow_type="leave_attendance",
        name="Leave & Attendance",
        description="Leave workflow",
        supported_request_hints=["leave"],
        required_agents=["orchestrator"],
        required_tool_capabilities=["employee.lookup"],
        memory_profile={"short_term": True},
        entry_node="orchestrator",
        terminal_statuses=["completed"],
        approval_outcomes=["pending_approval"],
        version="1.0",
    )
    assert spec.workflow_type == "leave_attendance"
    assert "leave" in spec.supported_request_hints
    assert LEAVE_WORKFLOW_SPEC.workflow_type == "leave_attendance"
    assert LEAVE_WORKFLOW_SPEC.entry_node == "orchestrator"


def test_registry_registration_and_lookup() -> None:
    registry = get_workflow_registry()
    types = registry.list_workflow_types()
    assert "leave_attendance" in types
    assert "recruitment" in types
    assert "onboarding" in types
    assert "attendance" in types
    assert "performance" in types
    assert "training" in types
    assert "offboarding" in types
    assert "hr_services" in types
    registered = registry.get("leave_attendance")
    assert registered.spec.name == "Leave & Attendance"
    assert registered.runner is not None
    specs = registry.list_workflows()
    assert {item.workflow_type for item in specs} >= {
        "leave_attendance",
        "recruitment",
        "onboarding",
        "attendance",
        "performance",
        "training",
        "offboarding",
        "hr_services",
    }


def test_registry_unknown_workflow() -> None:
    registry = get_workflow_registry()
    with pytest.raises(UnknownWorkflowError):
        registry.get("not_a_real_workflow")


def test_router_leave_classification() -> None:
    router = WorkflowRouter()
    result = router.classify(LEAVE_APPROVE)
    assert result.status == "routed"
    assert result.workflow_type == "leave_attendance"
    assert result.confidence > 0
    assert any("leave" in hint.lower() for hint in result.matched_hints)


def test_router_explicit_workflow_override() -> None:
    router = WorkflowRouter()
    result = router.classify(
        "Please handle this HR case for the team.",
        workflow_type="leave_attendance",
    )
    assert result.status == "routed"
    assert result.workflow_type == "leave_attendance"
    assert result.confidence == 1.0


def test_router_unsupported_request() -> None:
    router = WorkflowRouter()
    result = router.classify("Generate a marketing campaign for social media.")
    assert result.status == "unsupported"
    assert result.workflow_type == ""
    assert result.unsupported_reason


def test_engine_executes_leave_and_returns_workflow_result() -> None:
    engine = get_workflow_engine()
    result = engine.run(LEAVE_APPROVE)
    state = result.state
    assert state["workflow_type"] == "leave_attendance"
    assert state["decision"]["outcome"] == "approve"
    assert "action" in [item["agent"] for item in state["agent_outputs"]]
    assert isinstance(result.audit, WorkflowAuditSnapshot)
    assert isinstance(result.metrics, WorkflowRunMetrics)
    assert result.router is not None
    assert result.router.workflow_type == "leave_attendance"


def test_audit_snapshot_fields() -> None:
    result = get_workflow_engine().run(LEAVE_APPROVE)
    audit = result.audit
    assert audit.workflow_id == result.state["workflow_id"]
    assert audit.workflow_type == "leave_attendance"
    assert audit.started_at
    assert audit.completed_at
    assert audit.status
    assert audit.final_outcome == "approve"
    assert audit.agents_executed
    assert audit.tool_executions
    assert audit.memory_accesses
    assert audit.decision.get("outcome") == "approve"
    assert isinstance(audit.completed_actions, list)
    assert isinstance(audit.errors, list)


def test_metrics_fields() -> None:
    result = get_workflow_engine().run(LEAVE_APPROVE)
    metrics = result.metrics
    assert metrics.duration_ms >= 0
    assert metrics.agent_count >= 8
    assert metrics.tool_count >= 1
    assert 0.0 <= metrics.tool_success_rate <= 1.0
    assert metrics.retry_count >= 0
    assert metrics.validation_failed is False
    assert metrics.human_approval_required is False
    assert metrics.decision_confidence > 0
    assert metrics.action_success_rate > 0
    assert metrics.escalated is False
    assert metrics.workflow_type == "leave_attendance"
    assert metrics.status == result.state["status"]


def test_human_approval_state_preserved_via_engine() -> None:
    result = get_workflow_engine().run(LEAVE_APPROVAL)
    state = result.state
    assert state["decision"]["outcome"] == "pending_approval"
    assert state["status"] == "awaiting_human_approval"
    assert state["requires_human_approval"] is True
    assert "action" not in [item["agent"] for item in state["agent_outputs"]]
    assert result.metrics.human_approval_required is True
    assert result.audit.approval_checkpoint is not None
    assert result.audit.approval_checkpoint.get("status") == "awaiting"


def test_engine_resume_approval_executes_actions() -> None:
    engine = get_workflow_engine()
    paused = engine.run(LEAVE_APPROVAL)
    workflow_id = paused.state["workflow_id"]
    resumed = engine.resume(
        workflow_id,
        ApprovalDecision(approved=True, decided_by="manager-1", comment="OK"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert state["requires_human_approval"] is False
    assert state["completed_actions"]
    assert any(item.get("type") == "update_leave_balance" for item in state["completed_actions"])
    assert "action" in [item["agent"] for item in state["agent_outputs"]]


def test_engine_resume_rejection() -> None:
    engine = get_workflow_engine()
    paused = engine.run(LEAVE_APPROVAL)
    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=False, decided_by="manager-1", comment="Too long"),
    )
    assert resumed.state["decision"]["outcome"] == "reject"
    assert resumed.state["completed_actions"] == []
    assert resumed.state["status"] == "completed"


def test_engine_resume_missing_checkpoint() -> None:
    engine = get_workflow_engine()
    with pytest.raises(WorkflowResumeError):
        engine.resume("missing-id", ApprovalDecision(approved=True))


def test_organization_user_context_passthrough() -> None:
    result = get_workflow_engine().run(
        LEAVE_APPROVE,
        organization_id="org-demo",
        user_id="u-42",
        user_role="hr_admin",
    )
    state = result.state
    assert state["organization_id"] == "org-demo"
    assert state["user_id"] == "u-42"
    assert state["user_role"] == "hr_admin"
    assert state["decision"]["outcome"] == "approve"
    assert result.audit.organization_id == "org-demo"
    assert result.metrics.organization_id == "org-demo"


def test_engine_reject_path_unchanged() -> None:
    result = get_workflow_engine().run(LEAVE_REJECT)
    state = result.state
    assert state["decision"]["outcome"] == "reject"
    assert "action" not in [item["agent"] for item in state["agent_outputs"]]
    assert state["completed_actions"] == []


def test_decision_model_additive_fields() -> None:
    decision = WorkflowDecision(
        outcome="approve",
        rationale="ok",
        executable=True,
        evidence=["policy HR-LEAVE-001"],
        blockers=[],
        warnings=["prior overlap"],
        influenced_by=["mem-1"],
    )
    assert decision.evidence == ["policy HR-LEAVE-001"]
    assert decision.warnings == ["prior overlap"]
    assert decision.influenced_by == ["mem-1"]

    leave = LeaveDecision(
        outcome="reject",
        rationale="insufficient balance",
        employee_id="E002",
        requested_days=3,
        blockers=["insufficient balance"],
    )
    payload = leave.model_dump()
    assert payload["blockers"] == ["insufficient balance"]
    assert payload["evidence"] == []
    assert payload["employee_id"] == "E002"


def test_empty_registry_can_register_custom_future_type() -> None:
    """Registry/Router design accepts future types like attendance without redesign."""

    registry = WorkflowRegistry()
    spec = WorkflowSpec(
        workflow_type="attendance",
        name="Attendance",
        description="Future attendance workflow",
        supported_request_hints=["attendance pattern", "late arrivals"],
        version="0.0",
    )
    registry.register(spec, runner=lambda user_request, **kwargs: {"workflow_type": "attendance"})
    router = WorkflowRouter(registry)
    result = router.classify("Analyze late arrivals and attendance pattern for E003.")
    assert result.workflow_type == "attendance"
    assert result.status == "routed"
