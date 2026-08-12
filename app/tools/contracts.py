"""Project-owned tool contracts. Agents never call services directly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

# Domain categories for current and future HR tools. Only leave/employee/policy/
# notification tools are registered today.
ToolCategory = Literal[
    "employee",
    "policy",
    "leave",
    "attendance",
    "recruitment",
    "onboarding",
    "performance",
    "training",
    "offboarding",
    "notification",
    "documents",
    "analytics",
]
ToolSideEffect = Literal["read", "write"]


class ToolSpec(BaseModel):
    """Static description of a tool for registry, selection, and execution policy."""

    name: str
    description: str
    category: ToolCategory
    capability: str
    side_effect: ToolSideEffect
    allowed_agents: list[str]
    # Optional RBAC extension points. Empty means no extra role/org gate yet.
    allowed_roles: list[str] = Field(default_factory=list)
    requires_organization: bool = False
    idempotent: bool = False
    retryable: bool = False
    max_retries: int = Field(default=0, ge=0)
    timeout_seconds: float = Field(default=5.0, gt=0)


class ToolContext(BaseModel):
    """Runtime context for a single tool invocation.

    Organization/user fields are optional placeholders for multi-company tenancy.
    Existing leave workflows may leave them empty.
    """

    workflow_id: str
    agent: str
    workflow_type: str = ""
    organization_id: str = ""
    user_id: str = ""
    user_role: str = ""
    validated: bool = False


class BaseTool(ABC):
    """One enterprise capability. Implementations talk to services, not agents."""

    spec: ToolSpec
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    @abstractmethod
    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        """Run the tool and return output data, or raise a typed tool error."""
