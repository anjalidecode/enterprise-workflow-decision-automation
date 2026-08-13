"""Deterministic, policy-controlled tool selection. No LLM picking."""

from __future__ import annotations

from app.tools.contracts import BaseTool, ToolContext
from app.tools.errors import ToolForbiddenError, ToolNotFoundError
from app.tools.registry import ToolRegistry


class ToolSelector:
    """Resolve a capability or name to a tool, then enforce authorization policy.

    Authorization stages (Module 2):
    1. Agent allowlist
    2. Optional role allowlist (extension point; unused by leave tools today)
    3. Optional organization requirement (extension point)
    4. Write-tool validation gate
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def select(
        self,
        *,
        agent: str,
        capability: str | None = None,
        name: str | None = None,
        validated: bool = False,
        context: ToolContext | None = None,
    ) -> BaseTool:
        if not capability and not name:
            raise ToolNotFoundError("Tool selection requires a capability or a tool name.")

        if capability:
            tool = self._registry.find_by_capability(capability)
            if name and tool.spec.name != name:
                raise ToolNotFoundError(
                    f"Capability {capability} is bound to {tool.spec.name}, not {name}."
                )
        else:
            tool = self._registry.get(name or "")

        self._authorize(tool, agent=agent, validated=validated, context=context)
        return tool

    def _authorize(
        self,
        tool: BaseTool,
        *,
        agent: str,
        validated: bool,
        context: ToolContext | None,
    ) -> None:
        if agent not in tool.spec.allowed_agents:
            raise ToolForbiddenError(
                f"Agent '{agent}' is not allowed to use tool '{tool.spec.name}'."
            )

        if tool.spec.allowed_roles:
            role = (context.user_role if context is not None else "") or ""
            if not role or role not in tool.spec.allowed_roles:
                raise ToolForbiddenError(
                    f"Role '{role or '(none)'}' is not allowed to use tool '{tool.spec.name}'."
                )

        if tool.spec.requires_organization:
            organization_id = (context.organization_id if context is not None else "") or ""
            if not organization_id:
                raise ToolForbiddenError(
                    f"Tool '{tool.spec.name}' requires an organization_id in the tool context."
                )

        if tool.spec.side_effect == "write":
            write_agents = {
                "action",
                "recruitment_action",
                "onboarding_action",
                "attendance_action",
                "performance_action",
                "training_action",
            }
            if agent not in write_agents:
                raise ToolForbiddenError(
                    f"Write tool '{tool.spec.name}' can only be selected by an Action agent."
                )
            if not validated:
                raise ToolForbiddenError(
                    f"Write tool '{tool.spec.name}' requires a validated workflow decision."
                )
