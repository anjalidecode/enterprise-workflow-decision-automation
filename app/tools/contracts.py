"""Project-owned tool contracts. Agents never call services directly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

ToolCategory = Literal["employee", "policy", "leave", "notification"]
ToolSideEffect = Literal["read", "write"]


class ToolSpec(BaseModel):
    """Static description of a tool for registry, selection, and execution policy."""

    name: str
    description: str
    category: ToolCategory
    capability: str
    side_effect: ToolSideEffect
    allowed_agents: list[str]
    retryable: bool = False
    max_retries: int = Field(default=0, ge=0)
    timeout_seconds: float = Field(default=5.0, gt=0)


class ToolContext(BaseModel):
    """Runtime context for a single tool invocation."""

    workflow_id: str
    agent: str
    workflow_type: str = ""
    validated: bool = False


class BaseTool(ABC):
    """One enterprise capability. Implementations talk to services, not agents."""

    spec: ToolSpec
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    @abstractmethod
    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        """Run the tool and return output data, or raise a typed tool error."""
