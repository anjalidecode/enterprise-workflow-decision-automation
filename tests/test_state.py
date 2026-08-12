from app.orchestration.state import WorkflowState, create_initial_state


REQUIRED_KEYS = {
    "workflow_id",
    "user_request",
    "workflow_type",
    "current_stage",
    "status",
    "tasks",
    "completed_tasks",
    "employee_data",
    "retrieved_data",
    "policy_results",
    "analysis_results",
    "decision",
    "confidence",
    "pending_actions",
    "completed_actions",
    "errors",
    "requires_human_approval",
    "agent_outputs",
    "tool_executions",
    "metadata",
}


def test_create_initial_state_has_required_fields() -> None:
    request = "Check whether employee E001 can take 3 days of leave from 2026-08-17."
    state = create_initial_state(request)

    assert set(REQUIRED_KEYS).issubset(state.keys())
    assert state["user_request"] == request
    assert state["workflow_id"]
    assert state["status"] == "pending"
    assert state["current_stage"] == "start"
    assert state["completed_tasks"] == []
    assert state["agent_outputs"] == []
    assert state["tool_executions"] == []
    assert state["errors"] == []
    assert state["requires_human_approval"] is False
    assert state["confidence"] == 0.0


def test_workflow_state_is_typed_dict() -> None:
    assert issubclass(WorkflowState, dict)
