import json
from pathlib import Path

from langgraph.graph import END, START

from app.orchestration.state import create_initial_state
from app.services.hr_data import DATA_DIR, get_employee
from app.services.hr_store import get_hr_store
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


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions", [])]


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
    assert "get_employee" in _tool_names(result)


def test_valid_leave_request_produces_executable_decision_and_action() -> None:
    result = run_leave_workflow(VALID_REQUEST)
    names = _agent_names(result)

    assert result["decision"]["outcome"] == "approve"
    assert result["decision"]["executable"] is True
    assert result["requires_human_approval"] is False
    assert result["confidence"] > 0
    assert "action" in names
    assert result["completed_actions"]
    assert result["completed_actions"][0]["type"] == "update_leave_balance"
    assert result["completed_actions"][0]["previous_balance"] == 12
    assert result["completed_actions"][0]["new_balance"] == 9
    assert result["status"] == "completed"
    assert get_hr_store().get_employee("E001")["leave_balances"]["annual"] == 9

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
    assert "update_leave_balance" not in _tool_names(result)


def test_human_approval_request_skips_action() -> None:
    result = run_leave_workflow(APPROVAL_REQUEST)

    assert result["requires_human_approval"] is True
    assert result["decision"]["outcome"] == "pending_approval"
    assert result["decision"]["executable"] is False
    assert "action" not in _agent_names(result)
    assert result["status"] == "awaiting_human_approval"
    assert "update_leave_balance" not in _tool_names(result)


def test_unknown_employee_does_not_approve() -> None:
    result = run_leave_workflow(UNKNOWN_EMPLOYEE_REQUEST)

    assert result["employee_data"] == {}
    assert result["decision"]["outcome"] == "reject"
    assert "action" not in _agent_names(result)
    assert any("not found" in error.lower() for error in result["errors"])
    not_found = [
        trace
        for trace in result["tool_executions"]
        if trace.get("error_code") == "NOT_FOUND"
    ]
    assert not_found


def test_tool_failure_does_not_fabricate_employee_or_approve() -> None:
    store = get_hr_store()
    store.inject_error("get_employee", times=100)
    result = run_leave_workflow(VALID_REQUEST, reset_runtime=False)

    assert result["employee_data"] == {}
    assert result["decision"]["outcome"] != "approve"
    assert "action" not in _agent_names(result)
    assert any(trace.get("error_code") == "SERVICE_ERROR" for trace in result["tool_executions"])


def test_successful_update_changes_memory_but_not_seed_json() -> None:
    run_leave_workflow(VALID_REQUEST)
    assert get_hr_store().get_employee("E001")["leave_balances"]["annual"] == 9

    seed_path = Path(DATA_DIR) / "employees" / "employees.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    e001 = next(item for item in payload if item["employee_id"] == "E001")
    assert e001["leave_balances"]["annual"] == 12


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
    assert len(result["tool_executions"]) >= 2


def test_workflow_records_memory_accesses_and_long_term_outcome() -> None:
    result = run_leave_workflow(VALID_REQUEST)
    accesses = result.get("memory_accesses") or []
    assert accesses
    assert any(item["agent"] == "research" and item["layer"] == "long_term" for item in accesses)
    assert any(item["agent"] == "response" and item["layer"] == "long_term" and item["operation"] == "write" for item in accesses)

    from app.memory.long_term import get_long_term_store

    stored = get_long_term_store().query(employee_id="E001", workflow_type="leave_attendance")
    assert stored
    assert stored[-1].metadata["outcome"] == "approved"


def test_long_term_memory_persists_across_two_workflow_runs() -> None:
    first = run_leave_workflow(VALID_REQUEST)
    second = run_leave_workflow(VALID_REQUEST)
    assert first["workflow_id"] != second["workflow_id"]
    recalled = second["retrieved_data"].get("prior_outcomes", 0)
    assert recalled >= 1


def test_memory_cannot_override_insufficient_balance() -> None:
    from app.memory.facade import write_long_term

    seed = create_initial_state(INSUFFICIENT_REQUEST)
    seed["workflow_type"] = "leave_attendance"
    seed["metadata"] = {"leave_request": {"employee_id": "E002"}}
    write_long_term(
        seed,
        agent="response",
        payload={
            "employee_id": "E002",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 10,
            "start_date": "2026-01-01",
            "rationale_summary": "Historical approval must not override current policy.",
            "requires_human_approval": False,
        },
    )
    result = run_leave_workflow(INSUFFICIENT_REQUEST)
    assert result["decision"]["outcome"] == "reject"
    assert "action" not in _agent_names(result)


def test_overlapping_history_adds_warning_but_does_not_force_reject() -> None:
    from app.memory.facade import write_long_term

    seed = create_initial_state(VALID_REQUEST)
    seed["workflow_type"] = "leave_attendance"
    seed["metadata"] = {"leave_request": {"employee_id": "E001"}}
    write_long_term(
        seed,
        agent="response",
        payload={
            "employee_id": "E001",
            "workflow_type": "leave_attendance",
            "outcome": "approved",
            "days": 3,
            "start_date": "2026-08-17",
            "rationale_summary": "Previous overlapping leave.",
            "requires_human_approval": False,
        },
    )
    result = run_leave_workflow(VALID_REQUEST)
    warnings = result["analysis_results"].get("warnings") or []
    assert any("overlaps" in item.lower() for item in warnings)
    assert result["decision"]["outcome"] == "approve"
    assert result["confidence"] < 0.92
    assert any(item.get("influenced_decision") for item in result["memory_accesses"])
