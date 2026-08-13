from typing import Any

import pytest
from pydantic import BaseModel

from app.orchestration.state import create_initial_state
from app.services.hr_store import get_hr_store
from app.services.interfaces import HREmployeeService, NotificationServicePort
from app.services.notifications import get_notification_service
from app.tools.catalog import build_registry, get_registry
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.domains import PLANNED_TOOL_CAPABILITIES, planned_capabilities_for_category
from app.tools.errors import ToolForbiddenError, ToolNotFoundError, ToolServiceError
from app.tools.executor import ToolExecutor, invoke_tool
from app.tools.idempotency import build_idempotency_key
from app.tools.registry import ToolRegistry
from app.tools.selector import ToolSelector
from app.workflows.leave_workflow import run_leave_workflow


def _state(**kwargs: Any) -> dict:
    return create_initial_state(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
        **kwargs,
    )


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
    assert spec.allowed_roles == []
    assert spec.requires_organization is False


def test_registry_registration_and_lookup() -> None:
    registry = build_registry()
    assert registry.has("get_employee")
    assert registry.get("get_employee").spec.capability == "employee.lookup"
    assert registry.find_by_capability("leave.balance.update").spec.name == "update_leave_balance"
    write_names = {tool.spec.name for tool in registry.find_write_tools()}
    assert "update_leave_balance" in write_names
    assert "notify_employee" in write_names
    assert "shortlist_candidate" in write_names
    assert "schedule_interview" in write_names
    research_tools = {tool.spec.name for tool in registry.list_for_agent("research")}
    assert research_tools == {"get_employee", "get_leave_balance"}
    assert {tool.spec.name for tool in registry.list_by_category("leave")} == {
        "calculate_leave_impact",
        "update_leave_balance",
    }
    assert "employee" in registry.categories()
    assert "recruitment" in registry.categories()
    assert "attendance" in registry.categories()


def test_registry_unknown_tool_fails_closed() -> None:
    registry = build_registry()
    with pytest.raises(ToolNotFoundError, match="Unknown tool"):
        registry.get("totally_unknown_tool")
    with pytest.raises(ToolNotFoundError, match="Unknown capability"):
        registry.find_by_capability("calendar.schedule")


def test_planned_domains_are_documented_not_registered() -> None:
    registry = build_registry()
    # Leave/recruitment/onboarding/attendance tools are implemented; later domains stay docs-only.
    planned_performance = planned_capabilities_for_category("performance")
    assert planned_performance
    assert any(item["name"] == "search_candidates" for item in PLANNED_TOOL_CAPABILITIES)
    for item in planned_performance:
        assert not registry.has(item["name"])
    assert registry.has("search_candidates")
    assert registry.has("calculate_candidate_score")
    assert registry.has("create_onboarding_task")
    assert registry.has("request_system_access")
    assert registry.has("get_attendance_records")
    assert registry.has("create_attendance_review")


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


def test_selector_role_and_organization_extension_points() -> None:
    class RoleGatedTool(BaseTool):
        spec = ToolSpec(
            name="role_gated",
            description="test",
            category="analytics",
            capability="test.role_gated",
            side_effect="read",
            allowed_agents=["research"],
            allowed_roles=["hr_admin"],
            requires_organization=True,
        )
        input_model = BaseModel
        output_model = BaseModel

        def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
            return {"ok": True}

    registry = ToolRegistry()
    registry.register(RoleGatedTool())
    selector = ToolSelector(registry)
    context = ToolContext(
        workflow_id="wf-1",
        agent="research",
        organization_id="",
        user_role="employee",
    )
    with pytest.raises(ToolForbiddenError, match="Role"):
        selector.select(agent="research", name="role_gated", context=context)

    context.user_role = "hr_admin"
    with pytest.raises(ToolForbiddenError, match="organization_id"):
        selector.select(agent="research", name="role_gated", context=context)

    context.organization_id = "org-acme"
    tool = selector.select(agent="research", name="role_gated", context=context)
    assert tool.spec.name == "role_gated"


def test_executor_successful_execution_and_trace() -> None:
    state = _state(organization_id="org-acme", user_id="u-1", user_role="hr_admin")
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
    assert trace["organization_id"] == "org-acme"
    assert trace["user_id"] == "u-1"
    assert trace["workflow_id"] == state["workflow_id"]
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


def test_idempotency_key_includes_organization() -> None:
    left = build_idempotency_key(
        capability="leave.balance.update",
        workflow_id="wf-1",
        organization_id="org-a",
        employee_id="E001",
        days=3,
    )
    right = build_idempotency_key(
        capability="leave.balance.update",
        workflow_id="wf-1",
        organization_id="org-b",
        employee_id="E001",
        days=3,
    )
    assert left != right


def test_service_interfaces_are_satisfied_by_current_implementations() -> None:
    assert isinstance(get_hr_store(), HREmployeeService)
    assert isinstance(get_notification_service(), NotificationServicePort)


def test_organization_context_flows_through_leave_workflow() -> None:
    from app.workflows.leave_workflow import build_leave_workflow
    from app.orchestration.state import create_initial_state
    from app.memory.facade import reset_short_term_memory
    from app.services.hr_store import reset_hr_store
    from app.services.notifications import reset_notification_service

    reset_short_term_memory()
    reset_hr_store()
    reset_notification_service()
    state = create_initial_state(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
        organization_id="org-acme",
        user_id="u-hr-1",
        user_role="hr_admin",
    )
    result = build_leave_workflow().invoke(state)
    assert result["decision"]["outcome"] == "approve"
    assert result["completed_actions"]
    assert any(
        trace.get("organization_id") == "org-acme" and trace.get("user_id") == "u-hr-1"
        for trace in result["tool_executions"]
    )


def test_leave_scenarios_still_gate_actions() -> None:
    approved = run_leave_workflow(
        "Check whether employee E001 can take 3 days of leave from 2026-08-17."
    )
    rejected = run_leave_workflow(
        "Check whether employee E002 can take 3 days of leave from 2026-08-17."
    )
    pending = run_leave_workflow(
        "Check whether employee E001 can take 8 days of leave from 2026-08-17."
    )
    assert approved["decision"]["outcome"] == "approve"
    assert approved["completed_actions"]
    assert rejected["decision"]["outcome"] == "reject"
    assert rejected["completed_actions"] == []
    assert pending["decision"]["outcome"] == "pending_approval"
    assert pending["completed_actions"] == []
