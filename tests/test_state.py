from app.orchestration.state import WorkflowState, create_initial_state


REQUIRED_KEYS = {
    "workflow_id",
    "request_id",
    "user_request",
    "workflow_type",
    "organization_id",
    "user_id",
    "initiated_by",
    "user_role",
    "current_stage",
    "status",
    "tasks",
    "completed_tasks",
    "entities",
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
    "memory_accesses",
    "metadata",
    "created_at",
    "final_response",
}


def test_create_initial_state_has_required_fields() -> None:
    request = "Check whether employee E001 can take 3 days of leave from 2026-08-17."
    state = create_initial_state(request)

    assert set(REQUIRED_KEYS).issubset(state.keys())
    assert state["user_request"] == request
    assert state["workflow_id"]
    assert state["request_id"] == state["workflow_id"]
    assert state["status"] == "pending"
    assert state["current_stage"] == "start"
    assert state["organization_id"] == ""
    assert state["user_id"] == ""
    assert state["user_role"] == ""
    assert state["entities"] == {}
    assert state["created_at"]
    assert state["completed_tasks"] == []
    assert state["agent_outputs"] == []
    assert state["tool_executions"] == []
    assert state["memory_accesses"] == []
    assert state["errors"] == []
    assert state["requires_human_approval"] is False
    assert state["confidence"] == 0.0


def test_create_initial_state_accepts_organization_context() -> None:
    state = create_initial_state(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
        organization_id="org-acme",
        user_id="u-hr-1",
        user_role="hr_admin",
        initiated_by="u-hr-1",
        entities={"employee_id": "E001"},
    )
    assert state["organization_id"] == "org-acme"
    assert state["user_id"] == "u-hr-1"
    assert state["user_role"] == "hr_admin"
    assert state["initiated_by"] == "u-hr-1"
    assert state["entities"]["employee_id"] == "E001"


def test_workflow_state_is_typed_dict() -> None:
    assert issubclass(WorkflowState, dict)
