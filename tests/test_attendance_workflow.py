"""Attendance workflow tests."""

from __future__ import annotations

from app.knowledge.store import get_knowledge_store, reset_knowledge_store
from app.orchestration.state import create_initial_state
from app.services.attendance_store import get_attendance_store, reset_attendance_store
from app.tools.catalog import get_registry
from app.workflows.attendance_workflow import (
    ATTENDANCE_AGENT_NODES,
    build_attendance_graph,
    run_attendance_workflow,
)
from app.workflows.builtins import ATTENDANCE_WORKFLOW_SPEC
from app.workflows.contracts import ApprovalDecision
from app.workflows.engine import get_workflow_engine
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter

E003_REQUEST = "Analyze attendance for employee E003 for July 2026."
E004_REQUEST = "Analyze attendance for employee E004 for July 2026."
E005_REQUEST = "Analyze attendance for employee E005 for July 2026."
E001_REQUEST = "Analyze attendance for employee E001 for July 2026."
SCAN_REQUEST = "Find employees with attendance issues in July 2026."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs") or []]


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions") or []]


def test_attendance_workflow_spec() -> None:
    assert ATTENDANCE_WORKFLOW_SPEC.workflow_type == "attendance"
    assert "attendance" in ATTENDANCE_WORKFLOW_SPEC.supported_request_hints
    assert "attendance.policy.validate" in ATTENDANCE_WORKFLOW_SPEC.required_tool_capabilities
    assert ATTENDANCE_WORKFLOW_SPEC.entry_node == "attendance_planner"


def test_attendance_registry_registration() -> None:
    registry = get_workflow_registry()
    spec = registry.get_spec("attendance")
    assert spec.workflow_type == "attendance"
    assert "attendance" in registry.list_workflow_types()


def test_router_detects_attendance() -> None:
    result = WorkflowRouter().classify(E003_REQUEST)
    assert result.status == "routed"
    assert result.workflow_type == "attendance"


def test_explicit_attendance_workflow_selection() -> None:
    result = WorkflowRouter().classify(
        "Please process this HR case.",
        workflow_type="attendance",
    )
    assert result.workflow_type == "attendance"
    assert result.confidence == 1.0


def test_attendance_graph_has_specialized_nodes_and_branch() -> None:
    graph = build_attendance_graph()
    for name in ATTENDANCE_AGENT_NODES:
        assert name in graph.nodes
    assert "attendance_validation" in graph.branches


def test_attendance_record_retrieval() -> None:
    state = run_attendance_workflow(E003_REQUEST)
    records = (state.get("retrieved_data") or {}).get("attendance_records") or []
    assert len(records) == 23
    assert "get_attendance_records" in _tool_names(state)
    assert "get_employee" in _tool_names(state)


def test_attendance_summary_calculation() -> None:
    state = run_attendance_workflow(E003_REQUEST)
    summary = (state.get("analysis_results") or {}).get("summary") or {}
    assert summary.get("present_days") == 22
    assert summary.get("absent_days") == 1
    assert summary.get("late_arrivals") == 2
    assert summary.get("attendance_percentage") == 95.65
    assert "calculate_attendance_summary" in _tool_names(state)


def test_attendance_policy_retrieval_and_validation() -> None:
    state = run_attendance_workflow(E003_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("policy_id") == "HR-ATTEND-001"
    assert policy.get("severity") == "normal"
    assert "get_attendance_policy" in _tool_names(state)
    assert "validate_attendance_policy" in _tool_names(state)


def test_normal_attendance_path() -> None:
    result = get_workflow_engine().run(E003_REQUEST)
    state = result.state
    assert state["workflow_type"] == "attendance"
    assert state["decision"]["outcome"] == "recommend"
    assert state["decision"]["executable"] is False
    assert state["status"] == "completed"
    assert "attendance_action" not in _agent_names(state)
    assert state["completed_actions"] == []


def test_warning_attendance_path() -> None:
    result = get_workflow_engine().run(E004_REQUEST)
    state = result.state
    assert state["decision"]["outcome"] == "approve"
    assert state["decision"]["executable"] is True
    assert (state.get("policy_results") or {}).get("severity") == "warning"
    assert state["status"] == "completed"
    assert "attendance_action" in _agent_names(state)
    assert any(item.get("type") == "send_attendance_warning" for item in state["completed_actions"])
    assert any(item.get("type") == "create_attendance_review" for item in state["completed_actions"])


def test_serious_violation_path() -> None:
    result = get_workflow_engine().run(E005_REQUEST)
    state = result.state
    assert state["decision"]["outcome"] == "escalate"
    assert state["status"] == "awaiting_human_approval"
    assert state["requires_human_approval"] is True
    assert state["completed_actions"] == []
    assert "attendance_action" not in _agent_names(state)
    assert result.audit.approval_checkpoint is not None


def test_missing_attendance_data_path() -> None:
    state = run_attendance_workflow(E001_REQUEST)
    assert state["decision"]["outcome"] == "blocked"
    assert state["decision"]["executable"] is False
    assert "attendance_action" not in _agent_names(state)
    assert state["completed_actions"] == []


def test_warning_notification_and_manager_review() -> None:
    state = run_attendance_workflow(E004_REQUEST)
    assert "send_attendance_warning" in _tool_names(state)
    assert "create_attendance_review" in _tool_names(state)
    assert "notify_employee" in _tool_names(state)
    assert "update_attendance_status" in _tool_names(state)


def test_no_high_impact_action_before_approval() -> None:
    state = run_attendance_workflow(E005_REQUEST)
    assert state["requires_human_approval"] is True
    assert "create_attendance_review" not in _tool_names(state)
    assert "send_attendance_warning" not in _tool_names(state)
    assert "update_attendance_status" not in _tool_names(state)


def test_resume_approved_executes_attendance_actions() -> None:
    engine = get_workflow_engine()
    paused = engine.run(E005_REQUEST)
    assert paused.state["status"] == "awaiting_human_approval"

    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=True, decided_by="manager-1", comment="Review authorized"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert any(item.get("type") == "create_attendance_review" for item in state["completed_actions"])
    assert any(item.get("type") == "send_attendance_warning" for item in state["completed_actions"])
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])


def test_attendance_review_idempotent() -> None:
    store = reset_attendance_store()
    first = store.create_review(
        workflow_id="wf-att-1",
        employee_id="E004",
        reason="warning",
        severity="warning",
    )
    second = store.create_review(
        workflow_id="wf-att-1",
        employee_id="E004",
        reason="warning",
        severity="warning",
    )
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert first["review_id"] == second["review_id"]


def test_attendance_tool_failure_handling() -> None:
    reset_attendance_store()
    get_attendance_store().inject_error("get_records", times=3)
    state = create_initial_state(E003_REQUEST, workflow_type="attendance")
    from app.agents.attendance.research import attendance_research_agent

    patched = attendance_research_agent(
        {
            **state,
            "metadata": {
                "attendance_request": {
                    "employee_id": "E003",
                    "start_date": "2026-07-01",
                    "end_date": "2026-07-31",
                    "scan_issues": False,
                }
            },
            "entities": {"employee_id": "E003"},
        }
    )
    assert patched.get("errors")
    # Clean run still works after faults are exhausted/reset.
    reset_attendance_store()
    clean = run_attendance_workflow(E003_REQUEST)
    assert clean["decision"]["outcome"] == "recommend"


def test_attendance_memory_access_tracing() -> None:
    state = run_attendance_workflow(E003_REQUEST)
    accesses = state.get("memory_accesses") or []
    assert accesses
    layers = {item.get("layer") for item in accesses}
    assert "short_term" in layers
    assert "knowledge" in layers
    assert "long_term" in layers


def test_attendance_knowledge_retrieval() -> None:
    reset_knowledge_store()
    store = get_knowledge_store()
    hits = store.search(
        "late arrival manager review escalation",
        workflow_type="attendance",
    )
    assert hits
    state = run_attendance_workflow(E003_REQUEST)
    assert any(item.get("layer") == "knowledge" for item in state.get("memory_accesses") or [])


def test_attendance_organization_isolation() -> None:
    store = reset_attendance_store()
    # Seeded records have empty organization_id and match any org filter.
    acme = store.get_records(
        "E003",
        start_date="2026-07-01",
        end_date="2026-07-31",
        organization_id="acme",
    )
    assert len(acme) == 23
    other = store.get_records(
        "E003",
        start_date="2026-07-01",
        end_date="2026-07-31",
        organization_id="",
    )
    assert len(other) == 23

    # Explicit foreign-org record must not leak into another org query.
    store._records.append(
        {
            "employee_id": "E003",
            "date": "2026-07-02",
            "status": "absent",
            "check_in": None,
            "check_out": None,
            "late_minutes": 0,
            "organization_id": "other-co",
        }
    )
    filtered = store.get_records(
        "E003",
        start_date="2026-07-01",
        end_date="2026-07-31",
        organization_id="acme",
    )
    assert all(item.get("organization_id") in {"", "acme"} for item in filtered)


def test_attendance_scan_issues_path() -> None:
    result = get_workflow_engine().run(SCAN_REQUEST)
    state = result.state
    assert state["workflow_type"] == "attendance"
    assert state["decision"]["outcome"] == "recommend"
    findings = (state.get("analysis_results") or {}).get("issue_findings") or []
    assert findings
    ids = {item.get("employee_id") for item in findings}
    assert "E004" in ids
    assert "E005" in ids
    assert "find_attendance_issues" in _tool_names(state)


def test_attendance_tools_registered() -> None:
    registry = get_registry()
    for capability in (
        "attendance.records.get",
        "attendance.summary.calculate",
        "attendance.policy.lookup",
        "attendance.policy.validate",
        "attendance.issues.find",
        "attendance.review.create",
        "attendance.warning.send",
        "attendance.status.update",
    ):
        assert registry.find_by_capability(capability) is not None


def test_leave_recruitment_onboarding_regression() -> None:
    engine = get_workflow_engine()
    leave = engine.run(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17."
    )
    assert leave.state["workflow_type"] == "leave_attendance"
    assert leave.state["decision"]["outcome"] == "approve"

    recruitment = engine.run("Find candidates for job J001.")
    assert recruitment.state["workflow_type"] == "recruitment"

    onboarding = engine.run("Start onboarding for employee E003.")
    assert onboarding.state["workflow_type"] == "onboarding"
    assert onboarding.state["decision"]["outcome"] == "ready"
