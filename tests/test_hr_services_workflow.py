"""Employee HR Services workflow tests."""

from __future__ import annotations

from app.knowledge.store import get_knowledge_store, reset_knowledge_store
from app.orchestration.state import create_initial_state
from app.services.hr_services_store import get_hr_services_store, reset_hr_services_store
from app.tools.catalog import get_registry
from app.workflows.builtins import HR_SERVICES_WORKFLOW_SPEC
from app.workflows.contracts import ApprovalDecision
from app.workflows.engine import get_workflow_engine
from app.workflows.hr_services_workflow import (
    HR_SERVICES_AGENT_NODES,
    build_hr_services_graph,
    run_hr_services_workflow,
)
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter

LEAVE_BALANCE = "How many annual leave days does employee E001 have?"
ATTENDANCE = "Show my attendance summary for July for employee E003."
DOCUMENT = "Request an employment certificate for employee E003."
POLICY = "What is the attendance policy?"
BENEFITS = "How can I find information about employee benefits?"
PROFILE = "I need to update my phone number for employee E003."
PAYROLL = "I have a payroll issue for employee E003."
TRAINING = "What training programs are available for employee E003?"
ONBOARDING = "What is the status of onboarding for employee E003?"
RECRUITMENT = "Check recruitment status for candidate C001."
GENERAL = "Please open an HR support ticket for employee E002."
UNKNOWN = "Something strange is happening with my HR paperwork for employee E002."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs") or []]


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions") or []]


def test_hr_services_workflow_spec() -> None:
    assert HR_SERVICES_WORKFLOW_SPEC.workflow_type == "hr_services"
    assert "employment certificate" in HR_SERVICES_WORKFLOW_SPEC.supported_request_hints
    assert "payroll issue" in HR_SERVICES_WORKFLOW_SPEC.supported_request_hints
    assert "hr_service.request.create" in HR_SERVICES_WORKFLOW_SPEC.required_tool_capabilities
    assert HR_SERVICES_WORKFLOW_SPEC.entry_node == "hr_services_planner"


def test_hr_services_registry_registration() -> None:
    registry = get_workflow_registry()
    spec = registry.get_spec("hr_services")
    assert spec.workflow_type == "hr_services"
    assert "hr_services" in registry.list_workflow_types()


def test_router_detects_hr_services() -> None:
    result = WorkflowRouter().classify("Request an employment certificate for employee E003.")
    assert result.status == "routed"
    assert result.workflow_type == "hr_services"


def test_router_does_not_steal_attendance() -> None:
    result = WorkflowRouter().classify("check my attendance for irregularities")
    assert result.workflow_type == "attendance"


def test_explicit_hr_services_workflow_selection() -> None:
    result = WorkflowRouter().classify(
        "Please process this case.",
        workflow_type="hr_services",
    )
    assert result.workflow_type == "hr_services"
    assert result.confidence == 1.0


def test_hr_services_graph_has_specialized_nodes_and_branch() -> None:
    graph = build_hr_services_graph()
    for name in HR_SERVICES_AGENT_NODES:
        assert name in graph.nodes
    assert "service_validation" in graph.branches


def test_leave_balance_request() -> None:
    result = get_workflow_engine().run(LEAVE_BALANCE, workflow_type="hr_services")
    state = result.state
    assert state["workflow_type"] == "hr_services"
    assert (state.get("metadata") or {}).get("service_category") == "leave_balance"
    assert "get_leave_balance" in _tool_names(state)
    assert state["decision"]["outcome"] == "ready"
    assert state["status"] == "completed"
    balance = ((state.get("analysis_results") or {}).get("answer_payload") or {}).get("balance")
    assert balance == 12
    assert (state.get("metadata") or {}).get("decision_branch") == "resolve"


def test_attendance_request_via_hr_services() -> None:
    state = run_hr_services_workflow(ATTENDANCE)
    assert (state.get("metadata") or {}).get("service_category") == "attendance"
    assert "get_attendance_records" in _tool_names(state)
    assert "calculate_attendance_summary" in _tool_names(state)
    assert state["decision"]["outcome"] == "ready"


def test_employment_document_request() -> None:
    state = run_hr_services_workflow(DOCUMENT)
    assert (state.get("metadata") or {}).get("service_category") == "employment_document"
    assert state["decision"]["outcome"] == "ready"
    assert "create_hr_document_request" in _tool_names(state)
    docs = [
        item
        for item in state["completed_actions"]
        if item.get("type") == "create_hr_document_request"
    ]
    assert docs
    assert docs[0].get("document_type") == "employment_certificate"
    assert (state.get("metadata") or {}).get("decision_branch") == "create_ticket"


def test_policy_information_request() -> None:
    reset_knowledge_store()
    state = run_hr_services_workflow(POLICY)
    assert (state.get("metadata") or {}).get("service_category") == "policy_information"
    assert state["decision"]["outcome"] == "ready"
    assert state["final_response"]
    assert any("policy" in str(state["final_response"]).lower() for _ in [1])


def test_benefits_request() -> None:
    reset_knowledge_store()
    state = run_hr_services_workflow(BENEFITS)
    assert (state.get("metadata") or {}).get("service_category") == "benefits"
    assert state["decision"]["outcome"] == "ready"
    assert "benefit" in state["final_response"].lower() or "Benefits" in state["final_response"]


def test_profile_change_requires_approval() -> None:
    result = get_workflow_engine().run(PROFILE, workflow_type="hr_services")
    state = result.state
    assert (state.get("metadata") or {}).get("service_category") == "employee_profile"
    assert state["decision"]["outcome"] == "pending_approval"
    assert state["status"] == "awaiting_human_approval"
    assert state["requires_human_approval"] is True
    assert "service_action" not in _agent_names(state)


def test_payroll_issue_routing() -> None:
    state = run_hr_services_workflow(PAYROLL)
    assert (state.get("metadata") or {}).get("service_category") == "payroll_routing"
    assert state["decision"]["outcome"] == "ready"
    assert "create_hr_service_request" in _tool_names(state)
    assert "route_hr_service_to_hr" in _tool_names(state)
    assert (state.get("metadata") or {}).get("decision_branch") == "create_ticket"


def test_training_information_request() -> None:
    state = run_hr_services_workflow(TRAINING)
    assert (state.get("metadata") or {}).get("service_category") == "training"
    assert "search_training_catalog" in _tool_names(state)
    assert state["decision"]["outcome"] == "ready"


def test_onboarding_status_request() -> None:
    state = run_hr_services_workflow(ONBOARDING)
    assert (state.get("metadata") or {}).get("service_category") == "onboarding"
    assert "list_onboarding_tasks" in _tool_names(state)
    assert state["decision"]["outcome"] == "ready"


def test_recruitment_status_request() -> None:
    state = run_hr_services_workflow(RECRUITMENT)
    assert (state.get("metadata") or {}).get("service_category") == "recruitment_status"
    assert "get_candidate" in _tool_names(state)
    assert state["decision"]["outcome"] == "ready"


def test_general_hr_request() -> None:
    state = run_hr_services_workflow(GENERAL)
    assert (state.get("metadata") or {}).get("service_category") == "general_hr"
    assert "create_hr_service_request" in _tool_names(state)
    assert state["decision"]["outcome"] == "ready"


def test_unknown_request_creates_ticket() -> None:
    state = run_hr_services_workflow(UNKNOWN)
    assert (state.get("metadata") or {}).get("service_category") == "general_hr"
    assert "create_hr_service_request" in _tool_names(state)


def test_service_ticket_creation() -> None:
    state = run_hr_services_workflow(GENERAL)
    tickets = [
        item for item in state["completed_actions"] if item.get("type") == "create_hr_service_request"
    ]
    assert tickets
    assert tickets[0].get("request_id")


def test_document_request_creation() -> None:
    state = run_hr_services_workflow(DOCUMENT)
    assert any(item.get("type") == "create_hr_document_request" for item in state["completed_actions"])


def test_authorization_blocks_cross_employee() -> None:
    result = get_workflow_engine().run(
        "How many annual leave days does employee E001 have?",
        workflow_type="hr_services",
        user_id="E003",
        user_role="employee",
    )
    state = result.state
    assert state["decision"]["outcome"] == "blocked"
    assert state["completed_actions"] == []
    assert "get_leave_balance" not in _tool_names(state)


def test_cross_employee_allowed_for_hr_admin() -> None:
    result = get_workflow_engine().run(
        LEAVE_BALANCE,
        workflow_type="hr_services",
        user_id="U-HR",
        user_role="hr_admin",
    )
    state = result.state
    assert state["decision"]["outcome"] == "ready"
    assert "get_leave_balance" in _tool_names(state)


def test_organization_isolation() -> None:
    store = reset_hr_services_store()
    alpha = store.get_request("HSR-ORG-001", organization_id="org-alpha")
    assert alpha is not None
    leaked = store.get_request("HSR-ORG-001", organization_id="org-beta")
    assert leaked is None

    result = get_workflow_engine().run(
        DOCUMENT,
        workflow_type="hr_services",
        organization_id="org-alpha",
    )
    state = result.state
    assert state.get("organization_id") == "org-alpha"
    tickets = [
        item
        for item in state["completed_actions"]
        if item.get("type") == "create_hr_document_request"
    ]
    assert tickets
    assert tickets[0].get("organization_id") in {"", "org-alpha"}


def test_idempotent_service_request() -> None:
    store = reset_hr_services_store()
    first = store.create_request(
        employee_id="E003",
        category="general_hr",
        summary="idempotent demo",
        workflow_id="wf-hr-1",
    )
    second = store.create_request(
        employee_id="E003",
        category="general_hr",
        summary="idempotent demo",
        workflow_id="wf-hr-1",
    )
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert first["request_id"] == second["request_id"]


def test_tool_failure_handling() -> None:
    reset_hr_services_store()
    get_hr_services_store().inject_error("get_policy", times=2)
    state = create_initial_state(POLICY, workflow_type="hr_services")
    from app.agents.hr_services.service_policy import service_policy_agent

    patched = service_policy_agent(
        {
            **state,
            "metadata": {
                "hr_services_request": {"category": "policy_information", "employee_id": None},
                "authorization": {"allowed": True},
            },
            "retrieved_data": {"service_data": {}, "authorization": {"allowed": True}},
            "employee_data": {},
        }
    )
    assert patched.get("errors")


def test_memory_access_tracing() -> None:
    state = run_hr_services_workflow(LEAVE_BALANCE)
    accesses = state.get("memory_accesses") or []
    assert accesses
    agents = {item.get("agent") for item in accesses}
    assert "hr_services_planner" in agents
    assert "service_decision" in agents or "service_response" in agents


def test_knowledge_retrieval() -> None:
    reset_knowledge_store()
    store = get_knowledge_store()
    hits = store.search("service ticket lifecycle confidentiality", workflow_type="hr_services")
    assert hits
    state = run_hr_services_workflow(BENEFITS)
    assert any(item.get("layer") == "knowledge" for item in (state.get("memory_accesses") or []))


def test_human_approval_and_resume() -> None:
    engine = get_workflow_engine()
    paused = engine.run(PROFILE, workflow_type="hr_services")
    assert paused.state["status"] == "awaiting_human_approval"
    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=True, decided_by="hr-1", comment="Profile update approved"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert any(
        item.get("type") == "create_hr_service_request" for item in state["completed_actions"]
    )
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])


def test_notification_sent() -> None:
    state = run_hr_services_workflow(DOCUMENT)
    assert "notify_employee" in _tool_names(state)
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])


def test_leave_regression() -> None:
    result = get_workflow_engine().run("Approve 2 days annual leave for employee E001.")
    assert result.state["workflow_type"] == "leave_attendance"


def test_recruitment_regression() -> None:
    result = get_workflow_engine().run("Find candidates for the senior engineer job opening.")
    assert result.state["workflow_type"] == "recruitment"


def test_onboarding_regression() -> None:
    result = get_workflow_engine().run("Start onboarding for employee E003.")
    assert result.state["workflow_type"] == "onboarding"


def test_attendance_regression() -> None:
    result = get_workflow_engine().run("Review attendance issues for employee E003.")
    assert result.state["workflow_type"] == "attendance"


def test_performance_regression() -> None:
    result = get_workflow_engine().run("Prepare a performance review for employee E003.")
    assert result.state["workflow_type"] == "performance"


def test_training_regression() -> None:
    result = get_workflow_engine().run("Recommend training courses for employee E003 skill gap.")
    assert result.state["workflow_type"] == "training"


def test_offboarding_regression() -> None:
    result = get_workflow_engine().run("Start offboarding for employee E006.")
    assert result.state["workflow_type"] == "offboarding"


def test_hr_services_tools_registered() -> None:
    registry = get_registry()
    for name in (
        "create_hr_service_request",
        "get_hr_service_request",
        "update_hr_service_request",
        "create_hr_document_request",
        "route_hr_service_to_hr",
        "get_hr_service_policy",
        "validate_hr_service_policy",
        "evaluate_hr_service_authorization",
    ):
        assert registry.get(name)
