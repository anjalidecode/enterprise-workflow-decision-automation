"""Training workflow tests."""

from __future__ import annotations

from app.knowledge.store import get_knowledge_store, reset_knowledge_store
from app.orchestration.state import create_initial_state
from app.services.training_store import get_training_store, reset_training_store
from app.tools.catalog import get_registry
from app.workflows.builtins import TRAINING_WORKFLOW_SPEC
from app.workflows.contracts import ApprovalDecision
from app.workflows.engine import get_workflow_engine
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter
from app.workflows.training_workflow import (
    TRAINING_AGENT_NODES,
    build_training_graph,
    run_training_workflow,
)

E003_REQUEST = "Recommend training for employee E003."
E004_REQUEST = "Identify skill gaps for employee E004."
E005_REQUEST = "Create a training plan for employee E005."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs") or []]


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions") or []]


def test_training_workflow_spec() -> None:
    assert TRAINING_WORKFLOW_SPEC.workflow_type == "training"
    assert "training" in TRAINING_WORKFLOW_SPEC.supported_request_hints
    assert "skill gap" in TRAINING_WORKFLOW_SPEC.supported_request_hints
    assert "recommend training" in TRAINING_WORKFLOW_SPEC.supported_request_hints
    assert "training.policy.validate" in TRAINING_WORKFLOW_SPEC.required_tool_capabilities
    assert TRAINING_WORKFLOW_SPEC.entry_node == "training_planner"


def test_training_registry_registration() -> None:
    registry = get_workflow_registry()
    spec = registry.get_spec("training")
    assert spec.workflow_type == "training"
    assert "training" in registry.list_workflow_types()


def test_router_detects_training() -> None:
    result = WorkflowRouter().classify(E003_REQUEST)
    assert result.status == "routed"
    assert result.workflow_type == "training"


def test_explicit_training_workflow_selection() -> None:
    result = WorkflowRouter().classify(
        "Please process this HR case.",
        workflow_type="training",
    )
    assert result.workflow_type == "training"
    assert result.confidence == 1.0


def test_training_graph_has_specialized_nodes_and_branch() -> None:
    graph = build_training_graph()
    for name in TRAINING_AGENT_NODES:
        assert name in graph.nodes
    assert "training_validation" in graph.branches


def test_training_history_retrieval() -> None:
    state = run_training_workflow(E003_REQUEST)
    history = (state.get("retrieved_data") or {}).get("training_history") or []
    assert history
    assert any(item.get("course_id") == "T001" for item in history)
    assert "get_training_history" in _tool_names(state)
    assert "get_employee" in _tool_names(state)


def test_course_search() -> None:
    state = run_training_workflow(E003_REQUEST)
    assert "search_training_catalog" in _tool_names(state)
    matched = (state.get("retrieved_data") or {}).get("matched_courses") or []
    assert matched


def test_course_retrieval() -> None:
    state = run_training_workflow(E003_REQUEST)
    assert "get_training_course" in _tool_names(state)
    primary = (state.get("analysis_results") or {}).get("recommended_course") or {}
    assert primary.get("course_id")


def test_skill_gap_calculation() -> None:
    state = run_training_workflow(E003_REQUEST)
    gaps = (state.get("analysis_results") or {}).get("skill_gaps") or []
    skills = {str(item.get("skill") or "").lower() for item in gaps}
    assert "fastapi" in skills
    assert "docker" in skills
    assert "postgresql" in skills
    assert "calculate_skill_gap" in _tool_names(state)


def test_training_policy_retrieval() -> None:
    state = run_training_workflow(E003_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("policy_id") == "HR-TRAIN-001"
    assert "get_training_policy" in _tool_names(state)


def test_training_policy_validation() -> None:
    state = run_training_workflow(E003_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("severity") == "ready"
    assert "validate_training_policy" in _tool_names(state)


def test_suitable_course_recommendation() -> None:
    result = get_workflow_engine().run(E003_REQUEST)
    state = result.state
    assert state["workflow_type"] == "training"
    assert state["decision"]["outcome"] == "ready"
    primary = (state.get("analysis_results") or {}).get("recommended_course") or {}
    assert primary.get("course_id") in {"T002", "T003", "T005"}
    assert state["status"] == "completed"
    assert "training_action" in _agent_names(state)


def test_missing_prerequisite_blocked() -> None:
    store = reset_training_store()
    employee = {
        "employee_id": "E004",
        "employment_status": "active",
        "name": "Riley Morgan",
    }
    course = store.get_course("T002")
    assert course is not None
    validation = store.validate_training_policy(
        employee=employee,
        course=course,
        prerequisites=["Python"],
        employee_skills=[{"name": "SEO", "level": "intermediate"}],
    )
    assert validation["severity"] == "blocked"
    assert any("prerequisite" in str(item).lower() for item in validation["violations"])


def test_inactive_course_blocked() -> None:
    store = reset_training_store()
    employee = {
        "employee_id": "E003",
        "employment_status": "active",
        "name": "Sam Patel",
    }
    course = store.get_course("T099")
    assert course is not None
    validation = store.validate_training_policy(employee=employee, course=course)
    assert validation["severity"] == "blocked"
    assert any("inactive" in str(item).lower() for item in validation["violations"])


def test_approval_required_course() -> None:
    result = get_workflow_engine().run(E005_REQUEST)
    state = result.state
    primary = (state.get("analysis_results") or {}).get("recommended_course") or {}
    assert primary.get("course_id") == "T006"
    assert (state.get("policy_results") or {}).get("severity") == "pending_approval"
    assert state["decision"]["outcome"] == "pending_approval"
    assert state["status"] == "awaiting_human_approval"
    assert state["requires_human_approval"] is True
    assert result.audit.approval_checkpoint is not None


def test_no_enrollment_before_approval() -> None:
    state = run_training_workflow(E005_REQUEST)
    assert state["requires_human_approval"] is True
    assert "create_training_enrollment" not in _tool_names(state)
    assert "create_training_plan" not in _tool_names(state)
    assert "training_action" not in _agent_names(state)
    assert state["completed_actions"] == []
    pending_types = {item.get("type") for item in state.get("pending_actions") or []}
    assert pending_types <= {"request_human_approval"}


def test_approved_resume_enrollment() -> None:
    engine = get_workflow_engine()
    paused = engine.run(E005_REQUEST)
    assert paused.state["status"] == "awaiting_human_approval"

    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=True, decided_by="manager-1", comment="Training authorized"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert any(item.get("type") == "create_training_plan" for item in state["completed_actions"])
    assert any(item.get("type") == "create_training_enrollment" for item in state["completed_actions"])
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])
    enrollments = [
        item for item in state["completed_actions"] if item.get("type") == "create_training_enrollment"
    ]
    assert enrollments[0].get("course_id") == "T006"


def test_training_plan_creation() -> None:
    state = run_training_workflow(E003_REQUEST)
    assert "create_training_plan" in _tool_names(state)
    plans = [item for item in state["completed_actions"] if item.get("type") == "create_training_plan"]
    assert plans
    assert plans[0].get("plan_id")


def test_idempotent_enrollment() -> None:
    store = reset_training_store()
    first = store.create_enrollment(
        workflow_id="wf-train-1",
        employee_id="E003",
        course_id="T005",
        reason="skill gap",
    )
    second = store.create_enrollment(
        workflow_id="wf-train-1",
        employee_id="E003",
        course_id="T005",
        reason="skill gap",
    )
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert first["enrollment_id"] == second["enrollment_id"]

    first_plan = store.create_plan(
        workflow_id="wf-train-1",
        employee_id="E003",
        course_ids=["T005", "T003"],
        skill_gaps=["docker", "postgresql"],
        reason="skill gap",
    )
    second_plan = store.create_plan(
        workflow_id="wf-train-1",
        employee_id="E003",
        course_ids=["T005", "T003"],
        skill_gaps=["docker", "postgresql"],
        reason="skill gap",
    )
    assert first_plan["idempotent_replay"] is False
    assert second_plan["idempotent_replay"] is True
    assert first_plan["plan_id"] == second_plan["plan_id"]


def test_training_notification() -> None:
    state = run_training_workflow(E003_REQUEST)
    assert "notify_employee" in _tool_names(state)
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])


def test_training_tool_failure_handling() -> None:
    reset_training_store()
    get_training_store().inject_error("get_history", times=3)
    state = create_initial_state(E003_REQUEST, workflow_type="training")
    from app.agents.training.employee_research import training_research_agent

    patched = training_research_agent(
        {
            **state,
            "metadata": {
                "training_request": {
                    "employee_id": "E003",
                    "operation": "recommend",
                }
            },
            "entities": {"employee_id": "E003"},
        }
    )
    assert patched.get("errors")
    reset_training_store()
    clean = run_training_workflow(E003_REQUEST)
    assert clean["decision"]["outcome"] == "ready"


def test_training_memory_access_tracing() -> None:
    state = run_training_workflow(E003_REQUEST)
    accesses = state.get("memory_accesses") or []
    assert accesses
    layers = {item.get("layer") for item in accesses}
    assert "short_term" in layers
    assert "knowledge" in layers
    assert "long_term" in layers


def test_training_knowledge_retrieval() -> None:
    reset_knowledge_store()
    store = get_knowledge_store()
    hits = store.search(
        "training request procedure manager approval course selection",
        workflow_type="training",
    )
    assert hits
    state = run_training_workflow(E003_REQUEST)
    assert any(item.get("layer") == "knowledge" for item in state.get("memory_accesses") or [])


def test_training_organization_isolation() -> None:
    store = reset_training_store()
    acme = store.get_history("E003", organization_id="acme")
    assert acme
    store._history.append(
        {
            "record_id": "TH-OTHER",
            "employee_id": "E003",
            "organization_id": "other-co",
            "course_id": "T001",
            "title": "Other Org Course",
            "status": "completed",
        }
    )
    filtered = store.get_history("E003", organization_id="acme")
    assert all(item.get("organization_id") in {"", "acme"} for item in filtered)
    assert all(item.get("record_id") != "TH-OTHER" for item in filtered)


def test_e004_different_recommendation() -> None:
    state = run_training_workflow(E004_REQUEST)
    gaps = (state.get("analysis_results") or {}).get("skill_gaps") or []
    skills = {str(item.get("skill") or "").lower() for item in gaps}
    assert "digital analytics" in skills or "campaign analytics" in skills
    primary = (state.get("analysis_results") or {}).get("recommended_course") or {}
    assert primary.get("course_id") == "T007"
    assert state["decision"]["outcome"] == "ready"
    e003 = run_training_workflow(E003_REQUEST)
    e003_course = ((e003.get("analysis_results") or {}).get("recommended_course") or {}).get(
        "course_id"
    )
    assert e003_course != primary.get("course_id")


def test_training_tools_registered() -> None:
    registry = get_registry()
    for capability in (
        "training.history.get",
        "training.catalog.search",
        "training.course.get",
        "training.skill_gap.calculate",
        "training.policy.lookup",
        "training.policy.validate",
        "training.plan.create",
        "training.enrollment.create",
        "training.status.update",
    ):
        assert registry.find_by_capability(capability) is not None


def test_leave_recruitment_onboarding_attendance_performance_regression() -> None:
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

    performance = engine.run("Analyze performance for employee E003 for Q2 2026.")
    assert performance.state["workflow_type"] == "performance"
    assert performance.state["decision"]["outcome"] == "recommend"
