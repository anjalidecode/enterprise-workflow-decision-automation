from app.orchestration.state import create_initial_state
from app.services.errors import SimulatedServiceError
from app.services.notifications import get_notification_service
from app.tools.executor import invoke_tool


def test_notification_is_recorded() -> None:
    service = get_notification_service()
    record = service.send(
        employee_id="E001",
        message="Leave request approved.",
        workflow_id="wf-1",
    )
    assert record["status"] == "sent"
    assert service.sent[0]["employee_id"] == "E001"
    assert service.fallback_log == []


def test_notification_fallback_is_logged() -> None:
    service = get_notification_service()
    service.fail_next(1)
    try:
        service.send(employee_id="E001", message="hello", workflow_id="wf-1")
        raise AssertionError("expected SimulatedServiceError")
    except SimulatedServiceError:
        pass
    fallback = service.log_fallback(
        employee_id="E001",
        message="hello",
        workflow_id="wf-1",
    )
    assert fallback["source"] == "fallback_log"
    assert service.fallback_log[0]["status"] == "logged_fallback"


def test_executor_uses_notification_fallback_after_retries() -> None:
    service = get_notification_service()
    service.fail_next(5)
    state = create_initial_state("notify test")
    result, patch = invoke_tool(
        state,
        agent="action",
        name="notify_employee",
        payload={
            "employee_id": "E001",
            "message": "Leave request approved.",
            "workflow_id": state["workflow_id"],
        },
        validated=True,
    )
    assert result.success is True
    assert result.source == "fallback_log"
    assert result.attempts == 3
    assert service.sent == []
    assert service.fallback_log
    assert patch["tool_executions"][0]["success"] is True
