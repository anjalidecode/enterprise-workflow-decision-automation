from app.agents.contracts import CORE_AGENT_SPECS, get_agent_spec
from app.models.decision import (
    EXECUTABLE_OUTCOMES,
    HUMAN_APPROVAL_OUTCOMES,
    WorkflowDecision,
)
from app.models.leave import LeaveDecision
from app.workflows.leave_workflow import AGENT_NODES, run_leave_workflow


def test_core_agent_contracts_cover_leave_graph_nodes() -> None:
    for name in AGENT_NODES:
        spec = get_agent_spec(name)
        assert spec.name == name
        assert spec.responsibility
        assert name in CORE_AGENT_SPECS


def test_workflow_decision_supports_future_outcomes() -> None:
    for outcome in (
        "approve",
        "reject",
        "pending_approval",
        "escalate",
        "recommend",
        "ready",
        "blocked",
    ):
        decision = WorkflowDecision(
            outcome=outcome,  # type: ignore[arg-type]
            rationale="test",
            executable=outcome in EXECUTABLE_OUTCOMES,
            requires_human_approval=outcome in HUMAN_APPROVAL_OUTCOMES,
        )
        assert decision.outcome == outcome

    assert "approve" in EXECUTABLE_OUTCOMES
    assert "ready" in EXECUTABLE_OUTCOMES
    assert "pending_approval" in HUMAN_APPROVAL_OUTCOMES
    assert "escalate" in HUMAN_APPROVAL_OUTCOMES


def test_leave_decision_extends_workflow_decision() -> None:
    decision = LeaveDecision(
        outcome="approve",
        rationale="ok",
        executable=True,
        confidence=0.9,
        employee_id="E001",
        requested_days=3,
        entity_refs={"employee_id": "E001"},
        evidence=["balance check"],
        warnings=[],
        blockers=[],
        influenced_by=[],
    )
    payload = decision.model_dump()
    assert payload["outcome"] == "approve"
    assert payload["employee_id"] == "E001"
    assert payload["entity_refs"]["employee_id"] == "E001"
    assert payload["evidence"] == ["balance check"]
    assert issubclass(LeaveDecision, WorkflowDecision)


def test_leave_workflow_populates_entities_without_regression() -> None:
    result = run_leave_workflow(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17."
    )
    assert result["entities"].get("employee_id") == "E001"
    assert result["decision"]["outcome"] == "approve"
    assert result["organization_id"] == ""
    assert result["request_id"]
    assert result["created_at"]
