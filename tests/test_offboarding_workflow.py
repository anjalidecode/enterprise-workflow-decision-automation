"""Offboarding workflow tests."""

from __future__ import annotations

from app.knowledge.store import get_knowledge_store, reset_knowledge_store
from app.orchestration.state import create_initial_state
from app.services.offboarding_store import get_offboarding_store, reset_offboarding_store
from app.tools.catalog import get_registry
from app.workflows.builtins import OFFBOARDING_WORKFLOW_SPEC
from app.workflows.contracts import ApprovalDecision
from app.workflows.engine import get_workflow_engine
from app.workflows.offboarding_workflow import (
    OFFBOARDING_AGENT_NODES,
    build_offboarding_graph,
    run_offboarding_workflow,
)
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter

E006_REQUEST = "Start offboarding for employee E006."
E007_REQUEST = "Start offboarding for employee E007."
E008_REQUEST = "Start offboarding for employee E008."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs") or []]


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions") or []]


def test_offboarding_workflow_spec() -> None:
    assert OFFBOARDING_WORKFLOW_SPEC.workflow_type == "offboarding"
    assert "offboarding" in OFFBOARDING_WORKFLOW_SPEC.supported_request_hints
    assert "resignation" in OFFBOARDING_WORKFLOW_SPEC.supported_request_hints
    assert "exit checklist" in OFFBOARDING_WORKFLOW_SPEC.supported_request_hints
    assert "offboarding.policy.validate" in OFFBOARDING_WORKFLOW_SPEC.required_tool_capabilities
    assert OFFBOARDING_WORKFLOW_SPEC.entry_node == "offboarding_planner"


def test_offboarding_registry_registration() -> None:
    registry = get_workflow_registry()
    spec = registry.get_spec("offboarding")
    assert spec.workflow_type == "offboarding"
    assert "offboarding" in registry.list_workflow_types()


def test_router_detects_offboarding() -> None:
    result = WorkflowRouter().classify(E006_REQUEST)
    assert result.status == "routed"
    assert result.workflow_type == "offboarding"


def test_explicit_offboarding_workflow_selection() -> None:
    result = WorkflowRouter().classify(
        "Please process this HR case.",
        workflow_type="offboarding",
    )
    assert result.workflow_type == "offboarding"
    assert result.confidence == 1.0


def test_offboarding_graph_has_specialized_nodes_and_branch() -> None:
    graph = build_offboarding_graph()
    for name in OFFBOARDING_AGENT_NODES:
        assert name in graph.nodes
    assert "offboarding_validation" in graph.branches


def test_exit_record_retrieval() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    exit_record = (state.get("retrieved_data") or {}).get("exit_record") or {}
    assert exit_record.get("employee_id") == "E006"
    assert exit_record.get("exit_type") == "voluntary_resignation"
    assert "get_offboarding_exit" in _tool_names(state)
    assert "get_employee" in _tool_names(state)


def test_asset_retrieval() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    assets = (state.get("retrieved_data") or {}).get("assets") or []
    assert len(assets) >= 3
    assert "list_offboarding_assets" in _tool_names(state)


def test_handover_retrieval() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    handover = (state.get("retrieved_data") or {}).get("handover") or {}
    assert handover.get("employee_id") == "E006"
    assert "Nova Analytics Pipeline" in (handover.get("projects") or [])


def test_checklist_generation() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    checklist = (state.get("retrieved_data") or {}).get("checklist") or {}
    assert checklist.get("pending_tasks")
    assert "get_offboarding_checklist" in _tool_names(state)
    assert "asset_return" in (checklist.get("pending_tasks") or [])


def test_offboarding_policy_retrieval() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("policy_id") == "HR-OFFBOARD-001"
    assert "get_offboarding_policy" in _tool_names(state)


def test_offboarding_policy_validation() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("severity") == "ready"
    assert "validate_offboarding_policy" in _tool_names(state)


def test_normal_offboarding_path_e006() -> None:
    result = get_workflow_engine().run(E006_REQUEST)
    state = result.state
    assert state["workflow_type"] == "offboarding"
    assert state["decision"]["outcome"] == "ready"
    assert state["status"] == "completed"
    assert "offboarding_action" in _agent_names(state)
    assert (state.get("metadata") or {}).get("decision_branch") == "ready"


def test_missing_information_blocked_e007() -> None:
    result = get_workflow_engine().run(E007_REQUEST)
    state = result.state
    assert state["decision"]["outcome"] == "blocked"
    assert state["status"] == "completed"
    blockers = state["decision"].get("blockers") or []
    assert blockers
    assert any("mandatory" in str(item).lower() for item in blockers)
    assert "offboarding_action" not in _agent_names(state)
    assert state["completed_actions"] == []


def test_outstanding_assets_handled() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    warnings = (state.get("policy_results") or {}).get("warnings") or []
    assert any("asset" in str(item).lower() for item in warnings)
    returns = [
        item for item in state["completed_actions"] if item.get("type") == "request_asset_return"
    ]
    assert returns
    assert "request_asset_return" in _tool_names(state)


def test_handover_task_creation() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    handovers = [
        item
        for item in state["completed_actions"]
        if item.get("type") == "create_offboarding_handover"
    ]
    assert handovers
    assert handovers[0].get("handover_task_id")


def test_exit_interview_scheduling() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    interviews = [
        item for item in state["completed_actions"] if item.get("type") == "schedule_exit_interview"
    ]
    assert interviews
    assert interviews[0].get("status") == "scheduled"


def test_access_revocation_request_standard() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    access = [
        item
        for item in state["completed_actions"]
        if item.get("type") == "create_access_revoke_request"
    ]
    assert access
    assert access[0].get("privileged") is False
    assert "revocation_requested" in str(access[0].get("status"))


def test_human_approval_required_e008() -> None:
    result = get_workflow_engine().run(E008_REQUEST)
    state = result.state
    assert (state.get("policy_results") or {}).get("severity") == "pending_approval"
    assert state["decision"]["outcome"] == "pending_approval"
    assert state["status"] == "awaiting_human_approval"
    assert state["requires_human_approval"] is True
    assert result.audit.approval_checkpoint is not None
    assert (state.get("metadata") or {}).get("decision_branch") == "review"


def test_no_high_impact_action_before_approval() -> None:
    state = run_offboarding_workflow(E008_REQUEST)
    assert state["requires_human_approval"] is True
    assert "create_access_revoke_request" not in _tool_names(state)
    assert "create_offboarding_task" not in _tool_names(state)
    assert "offboarding_action" not in _agent_names(state)
    assert state["completed_actions"] == []
    pending_types = {item.get("type") for item in state.get("pending_actions") or []}
    assert pending_types <= {"request_human_approval"}


def test_approved_resume_path() -> None:
    engine = get_workflow_engine()
    paused = engine.run(E008_REQUEST)
    assert paused.state["status"] == "awaiting_human_approval"

    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=True, decided_by="hr-1", comment="Privileged exit approved"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert any(item.get("type") == "create_offboarding_task" for item in state["completed_actions"])
    assert any(item.get("type") == "request_asset_return" for item in state["completed_actions"])
    assert any(
        item.get("type") == "create_offboarding_handover" for item in state["completed_actions"]
    )
    assert any(item.get("type") == "schedule_exit_interview" for item in state["completed_actions"])
    access = [
        item
        for item in state["completed_actions"]
        if item.get("type") == "create_access_revoke_request"
    ]
    assert access
    assert any(item.get("privileged") is True for item in access)
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])


def test_idempotent_writes() -> None:
    store = reset_offboarding_store()
    first = store.create_task(
        workflow_id="wf-off-1",
        employee_id="E006",
        task_type="manager_review",
    )
    second = store.create_task(
        workflow_id="wf-off-1",
        employee_id="E006",
        task_type="manager_review",
    )
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert first["task_id"] == second["task_id"]

    first_return = store.request_asset_return(
        workflow_id="wf-off-1",
        employee_id="E006",
        asset_id="A-E006-01",
    )
    second_return = store.request_asset_return(
        workflow_id="wf-off-1",
        employee_id="E006",
        asset_id="A-E006-01",
    )
    assert first_return["idempotent_replay"] is False
    assert second_return["idempotent_replay"] is True


def test_offboarding_tool_failure_handling() -> None:
    reset_offboarding_store()
    get_offboarding_store().inject_error("get_exit", times=3)
    state = create_initial_state(E006_REQUEST, workflow_type="offboarding")
    from app.agents.offboarding.exit_details_research import exit_details_research_agent

    patched = exit_details_research_agent(
        {
            **state,
            "metadata": {
                "offboarding_request": {
                    "employee_id": "E006",
                    "operation": "start_offboarding",
                }
            },
            "entities": {"employee_id": "E006"},
            "employee_data": {"employee_id": "E006", "employment_status": "active"},
        }
    )
    assert patched.get("errors")
    reset_offboarding_store()
    clean = run_offboarding_workflow(E006_REQUEST)
    assert clean["decision"]["outcome"] == "ready"


def test_offboarding_memory_access_tracing() -> None:
    state = run_offboarding_workflow(E006_REQUEST)
    accesses = state.get("memory_accesses") or []
    assert accesses
    layers = {item.get("layer") for item in accesses}
    assert "short_term" in layers
    assert "knowledge" in layers
    assert "long_term" in layers


def test_offboarding_knowledge_retrieval() -> None:
    reset_knowledge_store()
    store = get_knowledge_store()
    hits = store.search(
        "resignation process exit checklist asset return access revocation",
        workflow_type="offboarding",
    )
    assert hits
    state = run_offboarding_workflow(E006_REQUEST)
    assert any(item.get("layer") == "knowledge" for item in state.get("memory_accesses") or [])


def test_offboarding_organization_isolation() -> None:
    store = reset_offboarding_store()
    default_exit = store.get_exit("E006", organization_id="")
    assert default_exit is not None
    assert default_exit.get("organization_id") in {"", None}

    isolated = store.get_exit("E006", organization_id="org-isolated")
    assert isolated is not None
    assert isolated.get("organization_id") == "org-isolated"
    assert isolated.get("requested_last_working_day") == "2026-07-31"

    default_assets = store.list_assets("E006", organization_id="")
    assert all(item.get("organization_id") in {"", None} for item in default_assets)
    assert all(item.get("asset_id") != "A-E006-ORG" for item in default_assets)


def test_offboarding_tools_registered() -> None:
    registry = get_registry()
    for capability in (
        "offboarding.exit.get",
        "offboarding.policy.lookup",
        "offboarding.policy.validate",
        "offboarding.checklist.get",
        "offboarding.task.create",
        "offboarding.asset.list",
        "offboarding.asset.return",
        "offboarding.handover.create",
        "offboarding.exit_interview.schedule",
        "offboarding.access.revoke_request",
        "offboarding.status.update",
    ):
        assert registry.find_by_capability(capability) is not None


def test_leave_recruitment_onboarding_attendance_performance_training_regression() -> None:
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

    training = engine.run("Recommend training for employee E003.")
    assert training.state["workflow_type"] == "training"
    assert training.state["decision"]["outcome"] == "ready"
