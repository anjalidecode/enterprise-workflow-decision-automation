from langgraph.graph import END, START

from app.orchestration.state import create_initial_state
from app.services.hr_data import get_employee
from app.workflows.leave_workflow import (
    AGENT_NODES,
    build_leave_graph,
    build_leave_workflow,
    run_leave_workflow,
)

VALID_REQUEST = "Check whether employee E001 can take 3 days of leave from 2026-08-17."
INSUFFICIENT_REQUEST = "Check whether employee E002 can take 3 days of leave from 2026-08-17."
APPROVAL_REQUEST = "Check whether employee E001 can take 8 days of leave from 2026-08-17."
UNKNOWN_EMPLOYEE_REQUEST = "Check whether employee E999 can take 3 days of leave from 2026-08-17."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs", [])]


def test_leave_workflow_graph_contains_specialized_nodes() -> None:
    graph = build_leave_graph()
    for name in AGENT_NODES:
        assert name in graph.nodes

    compiled = build_leave_workflow()
    for name in AGENT_NODES:
        assert name in compiled.nodes


def test_leave_workflow_has_conditional_branch_not_linear_only() -> None:
    graph = build_leave_graph()
    assert "validation" in graph.branches
    assert ("action", "response") in graph.edges
    assert (START, "orchestrator") in graph.edges
    assert ("response", END) in graph.edges


def test_multiple_agent_nodes_execute_and_update_state() -> None:
    result = run_leave_workflow(VALID_REQUEST)
    names = _agent_names(result)

    assert names[0] == "orchestrator"
    assert "planner" in names
    assert "research" in names
    assert "policy" in names
    assert "analysis" in names
    assert "decision" in names
    assert "validation" in names
    assert "response" in names
    assert len(set(names)) >= 8

    assert result["workflow_type"] == "leave_attendance"
    assert result["employee_data"]["employee_id"] == "E001"
    assert result["retrieved_data"]["found"] is True
    assert result["policy_results"]["policy_id"] == "HR-LEAVE-001"
    assert result["analysis_results"]["recommendation"] == "approve"
    assert result["decision"]["outcome"] == "approve"
    assert result["final_response"]


def test_valid_leave_request_produces_executable_decision_and_action() -> None:
    result = run_leave_workflow(VALID_REQUEST)
    names = _agent_names(result)

    assert result["decision"]["outcome"] == "approve"
    assert result["decision"]["executable"] is True
    assert result["requires_human_approval"] is False
    assert result["confidence"] > 0
    assert "action" in names
    assert result["completed_actions"]
    assert result["completed_actions"][0]["type"] == "simulate_leave_balance_update"
    assert result["completed_actions"][0]["previous_balance"] == 12
    assert result["completed_actions"][0]["new_balance"] == 9
    assert result["status"] == "completed"

    stored = get_employee("E001")
    assert stored is not None
    assert stored["leave_balances"]["annual"] == 12


def test_insufficient_leave_follows_response_path_without_action() -> None:
    result = run_leave_workflow(INSUFFICIENT_REQUEST)
    names = _agent_names(result)

    assert result["employee_data"]["employee_id"] == "E002"
    assert result["decision"]["outcome"] == "reject"
    assert result["analysis_results"]["sufficient_balance"] is False
    assert "action" not in names
    assert result["completed_actions"] == []
    assert result["metadata"]["route"] == "response"
    assert "rejected" in result["final_response"].lower()


def test_human_approval_request_skips_action() -> None:
    result = run_leave_workflow(APPROVAL_REQUEST)

    assert result["requires_human_approval"] is True
    assert result["decision"]["outcome"] == "pending_approval"
    assert result["decision"]["executable"] is False
    assert "action" not in _agent_names(result)
    assert result["status"] == "awaiting_human_approval"


def test_unknown_employee_does_not_approve() -> None:
    result = run_leave_workflow(UNKNOWN_EMPLOYEE_REQUEST)

    assert result["employee_data"] == {}
    assert result["decision"]["outcome"] == "reject"
    assert "action" not in _agent_names(result)
    assert any("not found" in error.lower() for error in result["errors"])


def test_workflow_is_not_a_single_chatbot_call() -> None:
    graph = build_leave_graph()
    result = run_leave_workflow(VALID_REQUEST)
    names = _agent_names(result)

    assert len(graph.nodes) >= 9
    assert len(names) >= 9
    assert names != ["orchestrator"]
    assert result["policy_results"] != result["analysis_results"]
    assert result["decision"] != result["policy_results"]
    assert create_initial_state(VALID_REQUEST)["decision"] == {}
