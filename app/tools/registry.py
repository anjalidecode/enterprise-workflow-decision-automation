"""Explicit tool registry. Unknown names fail closed."""

from __future__ import annotations

from app.tools.contracts import BaseTool, ToolCategory
from app.tools.errors import ToolNotFoundError


class ToolRegistry:
    """In-process catalog of registered tools. One name and capability per tool."""

    def __init__(self) -> None:
        self._by_name: dict[str, BaseTool] = {}
        self._by_capability: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        name = tool.spec.name
        capability = tool.spec.capability
        if name in self._by_name:
            raise ValueError(f"Tool already registered: {name}")
        if capability in self._by_capability:
            raise ValueError(f"Capability already registered: {capability}")
        self._by_name[name] = tool
        self._by_capability[capability] = tool

    def get(self, name: str) -> BaseTool:
        tool = self._by_name.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Unknown tool: {name}")
        return tool

    def has(self, name: str) -> bool:
        return name in self._by_name

    def list_for_agent(self, agent: str) -> list[BaseTool]:
        return [tool for tool in self._by_name.values() if agent in tool.spec.allowed_agents]

    def list_by_category(self, category: ToolCategory | str) -> list[BaseTool]:
        return [tool for tool in self._by_name.values() if tool.spec.category == category]

    def find_by_capability(self, capability: str) -> BaseTool:
        tool = self._by_capability.get(capability)
        if tool is None:
            raise ToolNotFoundError(f"Unknown capability: {capability}")
        return tool

    def find_write_tools(self) -> list[BaseTool]:
        return [tool for tool in self._by_name.values() if tool.spec.side_effect == "write"]

    def all_tools(self) -> list[BaseTool]:
        return list(self._by_name.values())

    def categories(self) -> list[str]:
        return sorted({tool.spec.category for tool in self._by_name.values()})
