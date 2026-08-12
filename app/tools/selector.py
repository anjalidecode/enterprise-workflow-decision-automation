"""Deterministic, policy-controlled tool selection. No LLM picking."""

from __future__ import annotations

from app.tools.contracts import BaseTool
from app.tools.errors import ToolForbiddenError, ToolNotFoundError
from app.tools.registry import ToolRegistry


class ToolSelector:
    """Resolve a capability or name to a tool, then enforce agent/write policy."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def select(
        self,
        *,
        agent: str,
        capability: str | None = None,
        name: str | None = None,
        validated: bool = False,
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

        self._authorize(tool, agent=agent, validated=validated)
        return tool

    def _authorize(self, tool: BaseTool, *, agent: str, validated: bool) -> None:
        if agent not in tool.spec.allowed_agents:
            raise ToolForbiddenError(
                f"Agent '{agent}' is not allowed to use tool '{tool.spec.name}'."
            )
        if tool.spec.side_effect == "write":
            if agent != "action":
                raise ToolForbiddenError(
                    f"Write tool '{tool.spec.name}' can only be selected by the Action Agent."
                )
            if not validated:
                raise ToolForbiddenError(
                    f"Write tool '{tool.spec.name}' requires a validated workflow decision."
                )
