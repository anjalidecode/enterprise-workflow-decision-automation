"""Workflow registry: register and resolve workflow implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from app.orchestration.state import WorkflowState
from app.tools.catalog import get_registry as get_tool_registry
from app.workflows.contracts import WorkflowSpec
from app.workflows.errors import UnknownWorkflowError, WorkflowRegistrationError

WorkflowRunner = Callable[..., WorkflowState]
GraphFactory = Callable[[], CompiledStateGraph]


@dataclass
class RegisteredWorkflow:
    """A WorkflowSpec bound to its runnable implementation."""

    spec: WorkflowSpec
    runner: WorkflowRunner
    graph_factory: GraphFactory | None = None


class WorkflowRegistry:
    """In-process registry of available HR workflows."""

    def __init__(self) -> None:
        self._workflows: dict[str, RegisteredWorkflow] = {}

    def register(
        self,
        spec: WorkflowSpec,
        *,
        runner: WorkflowRunner,
        graph_factory: GraphFactory | None = None,
        validate_tools: bool = False,
    ) -> None:
        if not spec.workflow_type:
            raise WorkflowRegistrationError("WorkflowSpec.workflow_type is required.")
        if spec.workflow_type in self._workflows:
            raise WorkflowRegistrationError(
                f"Workflow '{spec.workflow_type}' is already registered."
            )
        if validate_tools and spec.required_tool_capabilities:
            tool_registry = get_tool_registry()
            missing = [
                capability
                for capability in spec.required_tool_capabilities
                if tool_registry.find_by_capability(capability) is None
            ]
            if missing:
                raise WorkflowRegistrationError(
                    f"Workflow '{spec.workflow_type}' missing tools: {', '.join(missing)}"
                )
        self._workflows[spec.workflow_type] = RegisteredWorkflow(
            spec=spec,
            runner=runner,
            graph_factory=graph_factory,
        )

    def get(self, workflow_type: str) -> RegisteredWorkflow:
        try:
            return self._workflows[workflow_type]
        except KeyError as exc:
            raise UnknownWorkflowError(
                f"Unknown workflow type '{workflow_type}'. "
                f"Registered: {sorted(self._workflows)}"
            ) from exc

    def get_spec(self, workflow_type: str) -> WorkflowSpec:
        return self.get(workflow_type).spec

    def list_workflows(self) -> list[WorkflowSpec]:
        return [item.spec for item in self._workflows.values()]

    def list_workflow_types(self) -> list[str]:
        return sorted(self._workflows)

    def clear(self) -> None:
        self._workflows.clear()


_DEFAULT_REGISTRY: WorkflowRegistry | None = None


def get_workflow_registry() -> WorkflowRegistry:
    """Return the process-level registry, bootstrapping builtins on first use."""

    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        from app.workflows.builtins import register_builtin_workflows

        registry = WorkflowRegistry()
        register_builtin_workflows(registry)
        _DEFAULT_REGISTRY = registry
    return _DEFAULT_REGISTRY


def reset_workflow_registry() -> WorkflowRegistry:
    """Reset and re-register builtins. Used by tests."""

    global _DEFAULT_REGISTRY
    from app.workflows.builtins import register_builtin_workflows

    registry = WorkflowRegistry()
    register_builtin_workflows(registry)
    _DEFAULT_REGISTRY = registry
    return registry
