"""Performance workflow tests."""

from __future__ import annotations

from app.knowledge.store import get_knowledge_store, reset_knowledge_store
from app.orchestration.state import create_initial_state
from app.services.performance_store import get_performance_store, reset_performance_store
from app.tools.catalog import get_registry
from app.workflows.builtins import PERFORMANCE_WORKFLOW_SPEC
from app.workflows.contracts import ApprovalDecision
from app.workflows.engine import get_workflow_engine
from app.workflows.performance_workflow import (
    PERFORMANCE_AGENT_NODES,
    build_performance_graph,
    run_performance_workflow,
)
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter

E003_REQUEST = "Analyze performance for employee E003 for Q2 2026."
E004_REQUEST = "Analyze performance for employee E004 for Q2 2026."
E005_REQUEST = "Analyze performance for employee E005 for Q2 2026."
E001_REQUEST = "Analyze performance for employee E001 for Q2 2026."
SCAN_REQUEST = "Identify employees who need performance support."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs") or []]


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions") or []]


def test_performance_workflow_spec() -> None:
    assert PERFORMANCE_WORKFLOW_SPEC.workflow_type == "performance"
    assert "performance" in PERFORMANCE_WORKFLOW_SPEC.supported_request_hints
    assert "appraisal" in PERFORMANCE_WORKFLOW_SPEC.supported_request_hints
    assert "kpi" in PERFORMANCE_WORKFLOW_SPEC.supported_request_hints
    assert "improvement plan" in PERFORMANCE_WORKFLOW_SPEC.supported_request_hints
    assert "performance.policy.validate" in PERFORMANCE_WORKFLOW_SPEC.required_tool_capabilities
    assert PERFORMANCE_WORKFLOW_SPEC.entry_node == "performance_planner"


def test_performance_registry_registration() -> None:
    registry = get_workflow_registry()
    spec = registry.get_spec("performance")
    assert spec.workflow_type == "performance"
    assert "performance" in registry.list_workflow_types()


def test_router_detects_performance() -> None:
    result = WorkflowRouter().classify(E003_REQUEST)
    assert result.status == "routed"
    assert result.workflow_type == "performance"


def test_explicit_performance_workflow_selection() -> None:
    result = WorkflowRouter().classify(
        "Please process this HR case.",
        workflow_type="performance",
    )
    assert result.workflow_type == "performance"
    assert result.confidence == 1.0


def test_performance_graph_has_specialized_nodes_and_branch() -> None:
    graph = build_performance_graph()
    for name in PERFORMANCE_AGENT_NODES:
        assert name in graph.nodes
    assert "performance_validation" in graph.branches


def test_performance_record_retrieval() -> None:
    state = run_performance_workflow(E003_REQUEST)
    records = (state.get("retrieved_data") or {}).get("performance_records") or []
    assert len(records) == 1
    assert records[0]["employee_id"] == "E003"
    assert "get_performance_records" in _tool_names(state)
    assert "get_employee" in _tool_names(state)


def test_performance_goal_retrieval() -> None:
    state = run_performance_workflow(E003_REQUEST)
    goals = (state.get("retrieved_data") or {}).get("performance_goals") or []
    assert len(goals) == 4
    assert "get_performance_goals" in _tool_names(state)


def test_performance_summary_calculation() -> None:
    state = run_performance_workflow(E003_REQUEST)
    summary = (state.get("analysis_results") or {}).get("summary") or {}
    assert summary.get("goal_achievement_pct") == 100.0
    assert summary.get("completed_count") == 4
    assert summary.get("partial_count") == 0
    assert summary.get("unmet_count") == 0
    assert "calculate_performance_summary" in _tool_names(state)


def test_performance_policy_retrieval() -> None:
    state = run_performance_workflow(E003_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("policy_id") == "HR-PERF-001"
    assert "get_performance_policy" in _tool_names(state)


def test_performance_policy_validation() -> None:
    state = run_performance_workflow(E003_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("severity") == "strong"
    assert "validate_performance_policy" in _tool_names(state)


def test_strong_performance_path() -> None:
    result = get_workflow_engine().run(E003_REQUEST)
    state = result.state
    assert state["workflow_type"] == "performance"
    assert state["decision"]["outcome"] == "recommend"
    assert state["decision"]["executable"] is False
    assert (state.get("policy_results") or {}).get("severity") == "strong"
    assert state["status"] == "completed"
    assert "performance_action" not in _agent_names(state)
    assert state["completed_actions"] == []
    assert "positive" in (state.get("final_response") or "").lower()


def test_mixed_performance_path() -> None:
    result = get_workflow_engine().run(E004_REQUEST)
    state = result.state
    summary = (state.get("analysis_results") or {}).get("summary") or {}
    assert summary.get("goal_achievement_pct") == 76.25
    assert summary.get("partial_count") == 3
    assert (state.get("policy_results") or {}).get("severity") == "development"
    assert state["decision"]["outcome"] == "ready"
    assert state["decision"]["executable"] is True
    assert state["status"] == "completed"
    assert "performance_action" in _agent_names(state)


def test_serious_concern_path() -> None:
    result = get_workflow_engine().run(E005_REQUEST)
    state = result.state
    summary = (state.get("analysis_results") or {}).get("summary") or {}
    assert summary.get("goal_achievement_pct") == 34.9
    assert summary.get("unmet_count") == 2
    assert (state.get("policy_results") or {}).get("severity") == "escalation"
    assert state["decision"]["outcome"] == "escalate"
    assert state["status"] == "awaiting_human_approval"
    assert state["requires_human_approval"] is True
    assert state["completed_actions"] == []
    assert "performance_action" not in _agent_names(state)
    assert result.audit.approval_checkpoint is not None


def test_missing_performance_data_path() -> None:
    state = run_performance_workflow(E001_REQUEST)
    assert state["decision"]["outcome"] == "blocked"
    assert state["decision"]["executable"] is False
    assert "performance_action" not in _agent_names(state)
    assert state["completed_actions"] == []


def test_review_task_creation() -> None:
    state = run_performance_workflow(E004_REQUEST)
    assert "create_performance_review" in _tool_names(state)
    assert any(item.get("type") == "create_performance_review" for item in state["completed_actions"])


def test_improvement_plan_recommendation() -> None:
    state = run_performance_workflow(E004_REQUEST)
    assert "create_improvement_plan" in _tool_names(state)
    plans = [item for item in state["completed_actions"] if item.get("type") == "create_improvement_plan"]
    assert plans
    assert plans[0].get("disciplinary") is False
    assert plans[0].get("plan_type") == "development"


def test_human_approval_requirement() -> None:
    state = run_performance_workflow(E005_REQUEST)
    assert state["requires_human_approval"] is True
    assert state["status"] == "awaiting_human_approval"


def test_no_high_impact_action_before_approval() -> None:
    state = run_performance_workflow(E005_REQUEST)
    assert state["requires_human_approval"] is True
    assert "create_performance_review" not in _tool_names(state)
    assert "create_improvement_plan" not in _tool_names(state)
    assert "update_performance_status" not in _tool_names(state)
    tool_names = set(_tool_names(state))
    assert "terminate" not in tool_names
    assert "demote" not in tool_names
    pending_types = {item.get("type") for item in state.get("pending_actions") or []}
    assert pending_types <= {"request_human_approval"}


def test_resume_approved_executes_performance_actions() -> None:
    engine = get_workflow_engine()
    paused = engine.run(E005_REQUEST)
    assert paused.state["status"] == "awaiting_human_approval"

    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=True, decided_by="manager-1", comment="Review authorized"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert any(item.get("type") == "create_performance_review" for item in state["completed_actions"])
    assert any(item.get("type") == "create_improvement_plan" for item in state["completed_actions"])
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])
    plans = [item for item in state["completed_actions"] if item.get("type") == "create_improvement_plan"]
    assert plans[0].get("disciplinary") is False
    assert plans[0].get("plan_type") == "performance_improvement"


def test_idempotent_writes() -> None:
    store = reset_performance_store()
    first_review = store.create_review(
        workflow_id="wf-perf-1",
        employee_id="E004",
        reason="development",
        severity="development",
        review_period="2026-Q2",
    )
    second_review = store.create_review(
        workflow_id="wf-perf-1",
        employee_id="E004",
        reason="development",
        severity="development",
        review_period="2026-Q2",
    )
    assert first_review["idempotent_replay"] is False
    assert second_review["idempotent_replay"] is True
    assert first_review["review_id"] == second_review["review_id"]

    first_plan = store.create_improvement_plan(
        workflow_id="wf-perf-1",
        employee_id="E004",
        reason="development",
        plan_type="development",
        review_period="2026-Q2",
    )
    second_plan = store.create_improvement_plan(
        workflow_id="wf-perf-1",
        employee_id="E004",
        reason="development",
        plan_type="development",
        review_period="2026-Q2",
    )
    assert first_plan["idempotent_replay"] is False
    assert second_plan["idempotent_replay"] is True
    assert first_plan["plan_id"] == second_plan["plan_id"]


def test_performance_tool_failure_handling() -> None:
    reset_performance_store()
    get_performance_store().inject_error("get_records", times=3)
    state = create_initial_state(E003_REQUEST, workflow_type="performance")
    from app.agents.performance.research import performance_research_agent

    patched = performance_research_agent(
        {
            **state,
            "metadata": {
                "performance_request": {
                    "employee_id": "E003",
                    "review_period": "2026-Q2",
                    "previous_period": None,
                    "scan_support": False,
                    "operation": "analyze",
                }
            },
            "entities": {"employee_id": "E003"},
        }
    )
    assert patched.get("errors")
    reset_performance_store()
    clean = run_performance_workflow(E003_REQUEST)
    assert clean["decision"]["outcome"] == "recommend"


def test_performance_memory_access_tracing() -> None:
    state = run_performance_workflow(E003_REQUEST)
    accesses = state.get("memory_accesses") or []
    assert accesses
    layers = {item.get("layer") for item in accesses}
    assert "short_term" in layers
    assert "knowledge" in layers
    assert "long_term" in layers


def test_performance_knowledge_retrieval() -> None:
    reset_knowledge_store()
    store = get_knowledge_store()
    hits = store.search(
        "performance improvement process approval requirements",
        workflow_type="performance",
    )
    assert hits
    state = run_performance_workflow(E003_REQUEST)
    assert any(item.get("layer") == "knowledge" for item in state.get("memory_accesses") or [])


def test_performance_organization_isolation() -> None:
    store = reset_performance_store()
    acme = store.get_records(
        "E003",
        review_period="2026-Q2",
        organization_id="acme",
    )
    assert len(acme) == 1
    other = store.get_records(
        "E003",
        review_period="2026-Q2",
        organization_id="",
    )
    assert len(other) == 1

    store._records.append(
        {
            "employee_id": "E003",
            "review_period": "2026-Q2",
            "organization_id": "other-co",
            "kpis": {"quality_score": 1},
            "projects": [],
            "strengths": [],
            "improvement_areas": [],
            "skill_gaps": [],
        }
    )
    filtered = store.get_records(
        "E003",
        review_period="2026-Q2",
        organization_id="acme",
    )
    assert all(item.get("organization_id") in {"", "acme"} for item in filtered)
    assert len(filtered) == 1


def test_performance_support_scan_path() -> None:
    result = get_workflow_engine().run(SCAN_REQUEST)
    state = result.state
    assert state["workflow_type"] == "performance"
    assert state["decision"]["outcome"] == "recommend"
    findings = (state.get("analysis_results") or {}).get("support_findings") or []
    assert findings
    ids = {item.get("employee_id") for item in findings}
    assert "E004" in ids
    assert "E005" in ids
    assert "E003" not in ids
    assert "find_performance_support" in _tool_names(state)
    assert state["completed_actions"] == []


def test_performance_tools_registered() -> None:
    registry = get_registry()
    for capability in (
        "performance.records.get",
        "performance.goals.get",
        "performance.summary.calculate",
        "performance.policy.lookup",
        "performance.policy.validate",
        "performance.support.find",
        "performance.review.create",
        "performance.improvement_plan.create",
        "performance.status.update",
    ):
        assert registry.find_by_capability(capability) is not None


def test_leave_recruitment_onboarding_attendance_regression() -> None:
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

    attendance = engine.run("Analyze attendance for employee E003 for July 2026.")
    assert attendance.state["workflow_type"] == "attendance"
    assert attendance.state["decision"]["outcome"] == "recommend"
