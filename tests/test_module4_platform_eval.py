"""Module 4 platform evaluation: cross-workflow routing, contracts, isolation."""

from __future__ import annotations

import pytest

from app.memory.facade import write_long_term
from app.orchestration.state import create_initial_state
from app.services.attendance_store import reset_attendance_store
from app.services.hr_store import reset_hr_store
from app.services.performance_store import reset_performance_store
from app.workflows.contracts import (
    WorkflowAuditSnapshot,
    WorkflowResult,
    WorkflowRunMetrics,
    WorkflowSpec,
)
from app.workflows.engine import get_workflow_engine
from app.workflows.registry import WorkflowRegistry, get_workflow_registry
from app.workflows.router import WorkflowRouter

# Representative requests from the Module 4 evaluation brief.
ROUTING_CASES = [
    ("Check my leave balance.", "leave_attendance"),
    ("Analyze my attendance.", "attendance"),
    ("Review my performance.", "performance"),
    ("Recommend training.", "training"),
    ("Start onboarding.", "onboarding"),
    ("Start offboarding.", "offboarding"),
    ("Find candidates.", "recruitment"),
    ("Request an employment certificate.", "hr_services"),
    ("Explain the leave policy.", "leave_attendance"),
    ("Explain the attendance policy.", "attendance"),
    ("leave balance inquiry for employee E001", "hr_services"),
    ("attendance inquiry for employee E003", "hr_services"),
]

CLI_CASES = [
    (
        "Check whether employee E001 can take 3 days of leave.",
        "leave_attendance",
    ),
    (
        "Find candidates for the Python Backend Developer position.",
        "recruitment",
    ),
    ("Start onboarding for employee E003.", "onboarding"),
    (
        "Analyze attendance for employee E003 for July 2026.",
        "attendance",
    ),
    (
        "Analyze performance for employee E003 for Q2 2026.",
        "performance",
    ),
    ("Recommend training for employee E003.", "training"),
    ("Start offboarding for employee E006.", "offboarding"),
    (
        "Request an employment certificate for employee E003.",
        "hr_services",
    ),
]

ALL_TYPES = [
    "leave_attendance",
    "recruitment",
    "onboarding",
    "attendance",
    "performance",
    "training",
    "offboarding",
    "hr_services",
]


@pytest.mark.parametrize("request_text,expected", ROUTING_CASES)
def test_cross_workflow_routing_matrix(request_text: str, expected: str) -> None:
    result = WorkflowRouter().classify(request_text)
    assert result.status == "routed"
    assert result.workflow_type == expected


def test_hr_services_does_not_steal_domain_training() -> None:
    result = WorkflowRouter().classify("employee request for training")
    assert result.status == "routed"
    assert result.workflow_type == "training"


def test_router_needs_clarification_on_equal_scores() -> None:
    registry = WorkflowRegistry()
    registry.register(
        WorkflowSpec(
            workflow_type="alpha",
            name="Alpha",
            description="alpha",
            supported_request_hints=["shared phrase"],
        ),
        runner=lambda user_request, **kwargs: {},
    )
    registry.register(
        WorkflowSpec(
            workflow_type="beta",
            name="Beta",
            description="beta",
            supported_request_hints=["shared phrase"],
        ),
        runner=lambda user_request, **kwargs: {},
    )
    result = WorkflowRouter(registry).classify("Please handle shared phrase case.")
    assert result.status == "needs_clarification"
    assert result.workflow_type == ""
    assert "alpha" in result.unsupported_reason and "beta" in result.unsupported_reason


@pytest.mark.parametrize("request_text,expected", CLI_CASES)
def test_cli_representative_requests_route_and_return_workflow_result(
    request_text: str,
    expected: str,
) -> None:
    result = get_workflow_engine().run(request_text)
    assert isinstance(result, WorkflowResult)
    assert result.router is not None
    assert result.router.workflow_type == expected
    assert result.state["workflow_type"] == expected
    assert result.spec_version
    assert isinstance(result.audit, WorkflowAuditSnapshot)
    assert isinstance(result.metrics, WorkflowRunMetrics)
    assert result.audit.workflow_id == result.state["workflow_id"]
    assert result.audit.workflow_type == expected
    assert result.metrics.workflow_type == expected
    assert result.state["status"] in {
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    }


def test_all_registered_workflows_share_result_audit_metrics_contract() -> None:
    registry = get_workflow_registry()
    assert set(registry.list_workflow_types()) >= set(ALL_TYPES)

    samples = {
        "leave_attendance": "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
        "recruitment": "Find candidates for job J001.",
        "onboarding": "Start onboarding for employee E003.",
        "attendance": "Analyze attendance for employee E003 for July 2026.",
        "performance": "Analyze performance for employee E003 for Q2 2026.",
        "training": "Recommend training for employee E003.",
        "offboarding": "Start offboarding for employee E006.",
        "hr_services": "Request an employment certificate for employee E003.",
    }
    for workflow_type, request_text in samples.items():
        result = get_workflow_engine().run(request_text, workflow_type=workflow_type)
        assert isinstance(result, WorkflowResult)
        assert result.state["workflow_type"] == workflow_type
        audit = result.audit
        metrics = result.metrics
        assert audit.workflow_id
        assert audit.workflow_type == workflow_type
        assert audit.started_at
        assert audit.completed_at
        assert audit.status
        assert isinstance(audit.agents_executed, list) and audit.agents_executed
        assert isinstance(audit.tool_executions, list)
        assert isinstance(audit.memory_accesses, list)
        assert isinstance(audit.decision, dict)
        assert isinstance(audit.pending_actions, list)
        assert isinstance(audit.completed_actions, list)
        assert isinstance(audit.errors, list)
        assert metrics.duration_ms >= 0
        assert metrics.agent_count >= 1
        assert metrics.tool_count >= 0
        assert metrics.workflow_type == workflow_type
        assert metrics.status == result.state["status"]
        # Shared memory/knowledge path: every domain run should leave a trace.
        assert any(
            item.get("layer") in {"short_term", "knowledge", "long_term"}
            for item in result.state.get("memory_accesses") or []
        )


def test_organization_isolation_across_domain_stores() -> None:
    reset_hr_store()
    attendance = reset_attendance_store()
    performance = reset_performance_store()

    attendance._records.append(
        {
            "employee_id": "E001",
            "date": "2026-07-15",
            "status": "absent",
            "check_in": None,
            "check_out": None,
            "late_minutes": 0,
            "organization_id": "org-b",
        }
    )
    performance._records.append(
        {
            "employee_id": "E001",
            "organization_id": "org-b",
            "review_period": "2026-Q2",
            "kpis": {"quality_score": 10},
            "projects": [],
            "strengths": [],
            "improvement_areas": ["foreign org only"],
            "skill_gaps": [],
            "previous_outcome": "needs_improvement",
        }
    )

    org_a_attendance = attendance.get_records(
        "E001",
        start_date="2026-07-01",
        end_date="2026-07-31",
        organization_id="org-a",
    )
    assert all(item.get("organization_id") in {"", "org-a"} for item in org_a_attendance)
    assert not any(item.get("organization_id") == "org-b" for item in org_a_attendance)

    org_a_performance = performance.get_records(
        "E001",
        review_period="2026-Q2",
        organization_id="org-a",
    )
    assert all(item.get("organization_id") in {"", "org-a"} for item in org_a_performance)
    assert not any(item.get("organization_id") == "org-b" for item in org_a_performance)


def test_memory_cannot_override_policy_across_leave_and_attendance() -> None:
    """Memory may warn/explain; structured policy remains authoritative."""

    from app.workflows.leave_workflow import run_leave_workflow

    insufficient = "Check whether employee E002 can take 3 days of leave from 2026-08-17."
    seed = create_initial_state(insufficient, workflow_type="leave_attendance")
    seed["metadata"] = {"leave_request": {"employee_id": "E002"}}
    write_long_term(
        seed,
        agent="response",
        payload={
            "employee_id": "E002",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 3,
            "start_date": "2026-08-17",
            "rationale_summary": "Prior approval must not override insufficient balance.",
            "requires_human_approval": False,
        },
    )
    leave_state = run_leave_workflow(insufficient)
    assert leave_state["decision"]["outcome"] == "reject"
    assert "action" not in [item["agent"] for item in leave_state.get("agent_outputs") or []]

    # Attendance: seed a soft memory of "no issues" but policy still drives escalation for E003.
    from app.workflows.attendance_workflow import run_attendance_workflow

    attendance_request = "Analyze attendance for employee E003 for July 2026."
    att_seed = create_initial_state(attendance_request, workflow_type="attendance")
    att_seed["metadata"] = {"attendance_request": {"employee_id": "E003"}}
    write_long_term(
        att_seed,
        agent="response",
        payload={
            "employee_id": "E003",
            "workflow_type": "attendance",
            "outcome": "ready",
            "rationale_summary": "Historical clean attendance must not override current issues.",
            "requires_human_approval": False,
        },
    )
    attendance_state = run_attendance_workflow(attendance_request)
    outcome = attendance_state["decision"]["outcome"]
    assert outcome in {"pending_approval", "escalate", "recommend", "ready"}
    # E003 July data has irregularities; memory must not force a clean approve path.
    assert outcome != "approve" or attendance_state.get("requires_human_approval") is True


def test_engine_unsupported_and_explicit_selection() -> None:
    engine = get_workflow_engine()
    unsupported = engine.run("Generate a marketing campaign for social media.")
    assert unsupported.router is not None
    assert unsupported.router.status == "unsupported"
    assert isinstance(unsupported, WorkflowResult)
    assert unsupported.state["status"] == "unsupported"

    explicit = engine.run(
        "Please process this generic case.",
        workflow_type="hr_services",
    )
    assert explicit.router is not None
    assert explicit.router.workflow_type == "hr_services"
    assert explicit.router.confidence == 1.0
    assert explicit.state["workflow_type"] == "hr_services"
