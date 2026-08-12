"""Validate, authorize, execute, retry, log. Agents call invoke_tool only."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_none

from app.orchestration.state import WorkflowState
from app.tools.contracts import BaseTool, ToolContext
from app.tools.errors import (
    ToolError,
    ToolForbiddenError,
    ToolInvalidInputError,
    ToolNotFoundError,
    ToolSelectionError,
    ToolServiceError,
)
from app.tools.registry import ToolRegistry
from app.tools.results import ToolExecutionRecord, ToolResult
from app.tools.selector import ToolSelector


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SAFE_INPUT_KEYS = (
    "employee_id",
    "days",
    "leave_type",
    "start_date",
    "workflow_id",
    "organization_id",
    "policy_id",
    "job_id",
    "candidate_id",
    "recipient_id",
    "score",
    "slot",
)


def _input_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload[key] for key in SAFE_INPUT_KEYS if key in payload}


def _context_from_state(state: WorkflowState, *, agent: str, validated: bool) -> ToolContext:
    return ToolContext(
        workflow_id=state.get("workflow_id", ""),
        agent=agent,
        workflow_type=state.get("workflow_type", ""),
        organization_id=state.get("organization_id", "") or "",
        user_id=state.get("user_id", "") or state.get("initiated_by", "") or "",
        user_role=state.get("user_role", "") or "",
        validated=validated,
    )


def _trace(
    *,
    tool: BaseTool | None,
    context: ToolContext,
    result: ToolResult,
    payload: dict[str, Any],
) -> dict[str, Any]:
    record = ToolExecutionRecord(
        tool_name=result.tool_name,
        agent=context.agent,
        capability=tool.spec.capability if tool is not None else "",
        success=result.success,
        attempts=result.attempts,
        duration_ms=result.duration_ms,
        error_code=result.error_code,
        input_summary=_input_summary(payload),
        timestamp=_utc_now(),
        workflow_id=context.workflow_id,
        organization_id=context.organization_id,
        user_id=context.user_id,
    )
    return record.model_dump()


def _result_from_error(
    *,
    tool_name: str,
    error: ToolError,
    attempts: int,
    duration_ms: float,
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        success=False,
        error_code=error.error_code,  # type: ignore[arg-type]
        error_message=error.message,
        retryable=False,
        attempts=attempts,
        duration_ms=duration_ms,
        source="tool_layer",
    )


class ToolExecutor:
    """Runs a selected tool with validation, retries, and tracing."""

    def __init__(self, registry: ToolRegistry, selector: ToolSelector | None = None) -> None:
        self._registry = registry
        self._selector = selector or ToolSelector(registry)

    def invoke(
        self,
        state: WorkflowState,
        *,
        agent: str,
        payload: dict[str, Any],
        capability: str | None = None,
        name: str | None = None,
        validated: bool | None = None,
    ) -> tuple[ToolResult, dict[str, Any]]:
        """Select and execute a tool. Always goes through the selector."""

        if validated is None:
            validated = bool((state.get("metadata") or {}).get("validation", {}).get("passed"))

        context = _context_from_state(state, agent=agent, validated=validated)
        started = time.perf_counter()
        tool: BaseTool | None = None
        try:
            tool = self._selector.select(
                agent=agent,
                capability=capability,
                name=name,
                validated=validated,
                context=context,
            )
            result = self._execute(tool, payload, context, started)
        except (ToolForbiddenError, ToolSelectionError) as error:
            duration_ms = (time.perf_counter() - started) * 1000
            result = _result_from_error(
                tool_name=name or capability or "unknown",
                error=error,
                attempts=1,
                duration_ms=duration_ms,
            )
        except ToolNotFoundError as error:
            duration_ms = (time.perf_counter() - started) * 1000
            result = _result_from_error(
                tool_name=name or capability or "unknown",
                error=error,
                attempts=1,
                duration_ms=duration_ms,
            )
        except ToolInvalidInputError as error:
            duration_ms = (time.perf_counter() - started) * 1000
            result = _result_from_error(
                tool_name=tool.spec.name if tool is not None else (name or "unknown"),
                error=error,
                attempts=1,
                duration_ms=duration_ms,
            )

        patch = {
            "tool_executions": [
                _trace(tool=tool, context=context, result=result, payload=payload)
            ]
        }
        return result, patch

    def _execute(
        self,
        tool: BaseTool,
        payload: dict[str, Any],
        context: ToolContext,
        started: float,
    ) -> ToolResult:
        try:
            inputs = tool.input_model.model_validate(payload)
        except ValidationError as error:
            raise ToolInvalidInputError(str(error)) from error

        max_attempts = tool.spec.max_retries + 1 if tool.spec.retryable else 1
        attempts = 0
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(max_attempts),
                retry=retry_if_exception_type(ToolServiceError),
                wait=wait_none(),
                reraise=True,
            ):
                with attempt:
                    attempts = attempt.retry_state.attempt_number
                    data = tool.execute(inputs, context)
            duration_ms = (time.perf_counter() - started) * 1000
            return ToolResult(
                tool_name=tool.spec.name,
                success=True,
                data=data,
                attempts=attempts,
                duration_ms=duration_ms,
                source=(
                    (data or {}).get("source", "simulated_hr_store")
                    if isinstance(data, dict)
                    else "simulated_hr_store"
                ),
            )
        except ToolNotFoundError as error:
            duration_ms = (time.perf_counter() - started) * 1000
            return _result_from_error(
                tool_name=tool.spec.name,
                error=error,
                attempts=max(attempts, 1),
                duration_ms=duration_ms,
            )
        except ToolInvalidInputError as error:
            duration_ms = (time.perf_counter() - started) * 1000
            return _result_from_error(
                tool_name=tool.spec.name,
                error=error,
                attempts=max(attempts, 1),
                duration_ms=duration_ms,
            )
        except ToolServiceError as error:
            duration_ms = (time.perf_counter() - started) * 1000
            if tool.spec.capability.startswith("notification."):
                return self._notification_fallback(tool, inputs, context, attempts, duration_ms)
            return ToolResult(
                tool_name=tool.spec.name,
                success=False,
                error_code="SERVICE_ERROR",
                error_message=error.message,
                retryable=False,
                attempts=max(attempts, 1),
                duration_ms=duration_ms,
                source="simulated_hr_store",
            )

    def _notification_fallback(
        self,
        tool: BaseTool,
        inputs: Any,
        context: ToolContext,
        attempts: int,
        duration_ms: float,
    ) -> ToolResult:
        from app.services.notifications import get_notification_service

        payload = inputs.model_dump() if hasattr(inputs, "model_dump") else dict(inputs)
        record = get_notification_service().log_fallback(
            employee_id=str(payload.get("employee_id", "")),
            message=str(payload.get("message", "")),
            workflow_id=str(payload.get("workflow_id") or context.workflow_id),
            organization_id=context.organization_id,
        )
        return ToolResult(
            tool_name=tool.spec.name,
            success=True,
            data=record,
            attempts=max(attempts, 1),
            duration_ms=duration_ms,
            source="fallback_log",
        )


def invoke_tool(
    state: WorkflowState,
    *,
    agent: str,
    payload: dict[str, Any],
    capability: str | None = None,
    name: str | None = None,
    validated: bool | None = None,
    registry: ToolRegistry | None = None,
) -> tuple[ToolResult, dict[str, Any]]:
    """Public entry point. Agents must use this instead of calling services."""

    from app.tools.catalog import get_registry

    active_registry = registry or get_registry()
    executor = ToolExecutor(active_registry)
    return executor.invoke(
        state,
        agent=agent,
        payload=payload,
        capability=capability,
        name=name,
        validated=validated,
    )


def merge_tool_patches(*patches: dict[str, Any]) -> dict[str, Any]:
    """Combine multiple executor patches into one node update."""

    traces: list[dict[str, Any]] = []
    for patch in patches:
        traces.extend(patch.get("tool_executions") or [])
    return {"tool_executions": traces}
