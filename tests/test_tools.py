from typing import Any

import pytest
from pydantic import BaseModel

from app.orchestration.state import create_initial_state
from app.tools.catalog import build_registry, get_registry
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import ToolForbiddenError, ToolNotFoundError, ToolServiceError
from app.tools.executor import ToolExecutor, invoke_tool
from app.tools.registry import ToolRegistry
from app.tools.selector import ToolSelector


def _state() -> dict:
    return create_initial_state("Check whether employee E001 can take 3 days of leave from 2026-08-17.")


def test_tool_spec_contract_fields() -> None:
    spec = get_registry().get("get_employee").spec
    assert spec.name == "get_employee"
    assert spec.capability == "employee.lookup"
    assert spec.category == "employee"
    assert spec.side_effect == "read"
    assert "research" in spec.allowed_agents
    assert spec.retryable is True
    assert spec.max_retries >= 0
    assert spec.timeout_seconds > 0


def test_registry_registration_and_lookup() -> None:
    registry = build_registry()
    assert registry.has("get_employee")
    assert registry.get("get_employee").spec.capability == "employee.lookup"
    assert registry.find_by_capability("leave.balance.update").spec.name == "update_leave_balance"
    write_names = {tool.spec.name for tool in registry.find_write_tools()}
    assert write_names == {"update_leave_balance", "notify_employee"}
    research_tools = {tool.spec.name for tool in registry.list_for_agent("research")}
    assert research_tools == {"get_employee", "get_leave_balance"}


def test_registry_unknown_tool_fails_closed() -> None:
    registry = build_registry()
    with pytest.raises(ToolNotFoundError, match="Unknown tool"):
        registry.get("schedule_interview")
    with pytest.raises(ToolNotFoundError, match="Unknown capability"):
        registry.find_by_capability("calendar.schedule")


def test_selector_allows_read_tool_for_research() -> None:
    selector = ToolSelector(get_registry())
    tool = selector.select(agent="research", capability="employee.lookup")
    assert tool.spec.name == "get_employee"


def test_selector_forbids_agent_outside_allowlist() -> None:
    selector = ToolSelector(get_registry())
    with pytest.raises(ToolForbiddenError):
        selector.select(agent="research", capability="leave.balance.update", validated=True)


def test_selector_forbids_write_tool_without_validation() -> None:
    selector = ToolSelector(get_registry())
    with pytest.raises(ToolForbiddenError, match="validated"):
        selector.select(agent="action", name="update_leave_balance", validated=False)


def test_selector_allows_write_tool_after_validation() -> None:
    selector = ToolSelector(get_registry())
    tool = selector.select(agent="action", name="update_leave_balance", validated=True)
    assert tool.spec.side_effect == "write"


def test_selector_unknown_capability() -> None:
    selector = ToolSelector(get_registry())
    with pytest.raises(ToolNotFoundError, match="Unknown capability"):
        selector.select(agent="research", capability="calendar.schedule")


def test_executor_successful_execution_and_trace() -> None:
    state = _state()
    result, patch = invoke_tool(
        state,
        agent="research",
        capability="employee.lookup",
        payload={"employee_id": "E001"},
    )
    assert result.success is True
    assert result.data is not None
    assert result.data["employee_id"] == "E001"
    assert result.attempts == 1
    assert result.duration_ms >= 0
    trace = patch["tool_executions"][0]
    assert trace["tool_name"] == "get_employee"
    assert trace["agent"] == "research"
    assert trace["success"] is True
    assert "employee_id" in trace["input_summary"]


def test_executor_invalid_input_is_not_retried() -> None:
    state = _state()
    result, patch = invoke_tool(
        state,
        agent="research",
        capability="employee.lookup",
        payload={},
    )
    assert result.success is False
    assert result.error_code == "INVALID_INPUT"
    assert result.attempts == 1
    assert patch["tool_executions"][0]["error_code"] == "INVALID_INPUT"


def test_executor_not_found() -> None:
    state = _state()
    result, _patch = invoke_tool(
        state,
        agent="research",
        capability="employee.lookup",
        payload={"employee_id": "E999"},
    )
    assert result.success is False
    assert result.error_code == "NOT_FOUND"
    assert result.retryable is False


class _FlakyInput(BaseModel):
    value: str = "ok"


class _FlakyTool(BaseTool):
    spec = ToolSpec(
        name="flaky_read",
        description="Test-only retryable tool.",
        category="employee",
        capability="test.flaky",
        side_effect="read",
        allowed_agents=["research"],
        retryable=True,
        max_retries=2,
    )
    input_model = _FlakyInput
    output_model = _FlakyInput

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.failures:
            raise ToolServiceError("transient test failure")
        return {"value": "ok", "source": "test"}


def test_executor_retries_then_succeeds() -> None:
    registry = ToolRegistry()
    tool = _FlakyTool(failures=2)
    registry.register(tool)
    executor = ToolExecutor(registry)
    result, patch = executor.invoke(
        _state(),
        agent="research",
        capability="test.flaky",
        payload={"value": "ok"},
    )
    assert result.success is True
    assert result.attempts == 3
    assert tool.calls == 3
    assert patch["tool_executions"][0]["attempts"] == 3


def test_executor_retryable_failure_records_attempts() -> None:
    registry = ToolRegistry()
    tool = _FlakyTool(failures=5)
    registry.register(tool)
    executor = ToolExecutor(registry)
    result, _patch = executor.invoke(
        _state(),
        agent="research",
        capability="test.flaky",
        payload={"value": "ok"},
    )
    assert result.success is False
    assert result.error_code == "SERVICE_ERROR"
    assert result.attempts == 3
    assert tool.calls == 3
