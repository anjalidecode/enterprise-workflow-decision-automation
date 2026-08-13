"""Onboarding workflow tests."""

from __future__ import annotations

from app.knowledge.store import get_knowledge_store
from app.orchestration.state import create_initial_state
from app.services.onboarding_store import get_onboarding_store, reset_onboarding_store
from app.tools.catalog import get_registry
from app.workflows.builtins import ONBOARDING_WORKFLOW_SPEC
from app.workflows.contracts import ApprovalDecision
from app.workflows.engine import get_workflow_engine
from app.workflows.onboarding_workflow import (
    ONBOARDING_AGENT_NODES,
    build_onboarding_graph,
    run_onboarding_workflow,
)
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter

E003_REQUEST = "Start onboarding for employee E003."
E004_REQUEST = "Start onboarding for employee E004."
E005_REQUEST = "Start onboarding for employee E005."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs") or []]


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions") or []]


def test_onboarding_workflow_spec() -> None:
    assert ONBOARDING_WORKFLOW_SPEC.workflow_type == "onboarding"
    assert "onboarding" in ONBOARDING_WORKFLOW_SPEC.supported_request_hints
    assert "employee.document.verify" in ONBOARDING_WORKFLOW_SPEC.required_tool_capabilities
    assert ONBOARDING_WORKFLOW_SPEC.entry_node == "onboarding_planner"


def test_onboarding_registry_registration() -> None:
    registry = get_workflow_registry()
    spec = registry.get_spec("onboarding")
    assert spec.workflow_type == "onboarding"
    assert "onboarding" in registry.list_workflow_types()


def test_router_detects_onboarding() -> None:
    result = WorkflowRouter().classify(E003_REQUEST)
    assert result.status == "routed"
    assert result.workflow_type == "onboarding"


def test_explicit_onboarding_workflow_selection() -> None:
    result = WorkflowRouter().classify(
        "Please process this HR case.",
        workflow_type="onboarding",
    )
    assert result.workflow_type == "onboarding"
    assert result.confidence == 1.0


def test_onboarding_graph_has_specialized_nodes_and_branch() -> None:
    graph = build_onboarding_graph()
    for name in ONBOARDING_AGENT_NODES:
        assert name in graph.nodes
    assert "onboarding_validation" in graph.branches


def test_employee_lookup_via_tools() -> None:
    state = run_onboarding_workflow(E003_REQUEST)
    assert state["employee_data"]["employee_id"] == "E003"
    assert state["employee_data"]["role"] == "Software Engineer"
    assert state["employee_data"]["department"] == "Engineering"
    assert "get_employee" in _tool_names(state)


def test_document_retrieval_and_verification() -> None:
    state = run_onboarding_workflow(E003_REQUEST)
    verification = (state.get("retrieved_data") or {}).get("document_verification") or {}
    assert verification.get("all_mandatory_verified") is True
    assert "get_employee_documents" in _tool_names(state)
    assert "verify_employee_documents" in _tool_names(state)


def test_policy_retrieval() -> None:
    state = run_onboarding_workflow(E003_REQUEST)
    policy = state.get("policy_results") or {}
    assert policy.get("policy_id") == "HR-ONBOARD-001"
    assert "get_onboarding_policy" in _tool_names(state)
    assert "validate_onboarding_policy" in _tool_names(state)


def test_complete_employee_ready_path() -> None:
    result = get_workflow_engine().run(E003_REQUEST)
    state = result.state
    assert state["workflow_type"] == "onboarding"
    assert state["decision"]["outcome"] == "ready"
    assert state["decision"]["executable"] is True
    assert state["status"] == "completed"
    assert "onboarding_action" in _agent_names(state)
    assert any(item.get("type") == "create_onboarding_task" for item in state["completed_actions"])
    assert any(item.get("type") == "request_equipment" for item in state["completed_actions"])
    assert any(item.get("type") == "request_system_access" for item in state["completed_actions"])
    assert any(item.get("type") == "update_onboarding_status" for item in state["completed_actions"])
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])


def test_missing_document_blocked_path() -> None:
    state = run_onboarding_workflow(E004_REQUEST)
    assert state["decision"]["outcome"] == "blocked"
    assert state["decision"]["executable"] is False
    missing = (state.get("analysis_results") or {}).get("missing_documents") or []
    invalid = (state.get("analysis_results") or {}).get("invalid_documents") or []
    assert "education_certificate" in missing
    assert "tax_document" in invalid
    assert "onboarding_action" not in _agent_names(state)
    assert state["completed_actions"] == []
    assert "create_onboarding_task" not in _tool_names(state)
    assert "request_equipment" not in _tool_names(state)


def test_privileged_access_pending_approval() -> None:
    result = get_workflow_engine().run(E005_REQUEST)
    state = result.state
    assert state["decision"]["outcome"] == "pending_approval"
    assert state["status"] == "awaiting_human_approval"
    assert state["requires_human_approval"] is True
    assert state["completed_actions"] == []
    assert "onboarding_action" not in _agent_names(state)
    assert "production_admin" in (
        (state.get("analysis_results") or {}).get("privileged_access_required") or []
    )
    assert result.audit.approval_checkpoint is not None


def test_resume_approved_executes_onboarding_actions() -> None:
    engine = get_workflow_engine()
    paused = engine.run(E005_REQUEST)
    assert paused.state["status"] == "awaiting_human_approval"

    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=True, decided_by="hr-admin-1", comment="Privileged access OK"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert any(item.get("type") == "create_onboarding_task" for item in state["completed_actions"])
    assert any(item.get("type") == "request_equipment" for item in state["completed_actions"])
    assert any(item.get("type") == "request_system_access" for item in state["completed_actions"])
    privileged = [
        item
        for item in state["completed_actions"]
        if item.get("type") == "request_system_access" and item.get("privileged")
    ]
    assert privileged
    assert any(item.get("type") == "notify_employee" for item in state["completed_actions"])


def test_onboarding_task_equipment_access_idempotent() -> None:
    store = reset_onboarding_store()
    t1 = store.create_task(
        workflow_id="wf-ob-1",
        employee_id="E003",
        task_type="hr_orientation",
    )
    t2 = store.create_task(
        workflow_id="wf-ob-1",
        employee_id="E003",
        task_type="hr_orientation",
    )
    assert t1["idempotent_replay"] is False
    assert t2["idempotent_replay"] is True

    e1 = store.request_equipment(
        workflow_id="wf-ob-1",
        employee_id="E003",
        item="laptop",
    )
    e2 = store.request_equipment(
        workflow_id="wf-ob-1",
        employee_id="E003",
        item="laptop",
    )
    assert e1["idempotent_replay"] is False
    assert e2["idempotent_replay"] is True

    a1 = store.request_access(
        workflow_id="wf-ob-1",
        employee_id="E003",
        system="email",
    )
    a2 = store.request_access(
        workflow_id="wf-ob-1",
        employee_id="E003",
        system="email",
    )
    assert a1["idempotent_replay"] is False
    assert a2["idempotent_replay"] is True

    s1 = store.update_status(
        workflow_id="wf-ob-1",
        employee_id="E003",
        status="in_progress",
    )
    s2 = store.update_status(
        workflow_id="wf-ob-1",
        employee_id="E003",
        status="in_progress",
    )
    assert s1["idempotent_replay"] is False
    assert s2["idempotent_replay"] is True


def test_tool_failure_handling_for_documents() -> None:
    reset_onboarding_store()
    get_onboarding_store().inject_error("list_documents", times=3)
    state = create_initial_state(E003_REQUEST, workflow_type="onboarding")
    state["entities"] = {"employee_id": "E003"}
    from app.agents.onboarding.document_verification import document_verification_agent

    patch = document_verification_agent(state)
    assert patch.get("errors")
    reset_onboarding_store()
    clean = run_onboarding_workflow(E003_REQUEST)
    assert (clean.get("retrieved_data") or {}).get("document_verification", {}).get(
        "all_mandatory_verified"
    )


def test_memory_and_knowledge_recorded() -> None:
    result = get_workflow_engine().run(E003_REQUEST)
    accesses = result.state.get("memory_accesses") or []
    layers = {item.get("layer") for item in accesses}
    assert "short_term" in layers
    assert "knowledge" in layers
    assert any(item.get("layer") == "long_term" for item in accesses)

    hits = get_knowledge_store().search(
        "onboarding process document verification",
        workflow_type="onboarding",
    )
    assert hits


def test_organization_context_preserved() -> None:
    result = get_workflow_engine().run(
        E003_REQUEST,
        organization_id="org-acme",
        user_id="hr-9",
        user_role="hr_admin",
    )
    assert result.state["organization_id"] == "org-acme"
    assert result.state["user_id"] == "hr-9"
    assert result.audit.organization_id == "org-acme"
    assert result.metrics.organization_id == "org-acme"


def test_onboarding_tools_registered() -> None:
    registry = get_registry()
    for capability in (
        "employee.documents",
        "employee.document.verify",
        "onboarding.policy.lookup",
        "onboarding.policy.validate",
        "onboarding.task.create",
        "onboarding.task.list",
        "onboarding.equipment.request",
        "onboarding.access.request",
        "onboarding.status.update",
    ):
        assert registry.find_by_capability(capability) is not None


def test_leave_regression_unchanged() -> None:
    engine = get_workflow_engine()
    approve = engine.run(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17."
    )
    assert approve.state["decision"]["outcome"] == "approve"
    assert approve.state["completed_actions"]

    reject = engine.run(
        "Check whether employee E002 can take 3 days of leave from 2026-08-17."
    )
    assert reject.state["decision"]["outcome"] == "reject"
    assert reject.state["completed_actions"] == []

    pending = engine.run(
        "Check whether employee E001 can take 8 days of leave from 2026-08-17."
    )
    assert pending.state["status"] == "awaiting_human_approval"
    assert pending.state["completed_actions"] == []


def test_recruitment_regression_unchanged() -> None:
    result = get_workflow_engine().run(
        "Find candidates for the Python Backend Developer position."
    )
    assert result.state["workflow_type"] == "recruitment"
    assert result.state["decision"]["outcome"] == "pending_approval"
    assert result.state["status"] == "awaiting_human_approval"
