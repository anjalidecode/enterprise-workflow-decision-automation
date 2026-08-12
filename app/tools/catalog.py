"""Explicit registration of Module 2 leave-workflow tools."""

from __future__ import annotations

from app.tools.implementations.employee import GetEmployeeTool, GetLeaveBalanceTool
from app.tools.implementations.leave import CalculateLeaveImpactTool, UpdateLeaveBalanceTool
from app.tools.implementations.notification import NotifyEmployeeTool
from app.tools.implementations.policy import GetLeavePolicyTool, ValidateLeavePolicyTool
from app.tools.registry import ToolRegistry

_REGISTRY: ToolRegistry | None = None


def build_registry() -> ToolRegistry:
    """Create a new registry with the seven leave-workflow tools."""

    registry = ToolRegistry()
    registry.register(GetEmployeeTool())
    registry.register(GetLeaveBalanceTool())
    registry.register(GetLeavePolicyTool())
    registry.register(ValidateLeavePolicyTool())
    registry.register(CalculateLeaveImpactTool())
    registry.register(UpdateLeaveBalanceTool())
    registry.register(NotifyEmployeeTool())
    return registry


def get_registry() -> ToolRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_registry()
    return _REGISTRY


def reset_registry() -> ToolRegistry:
    global _REGISTRY
    _REGISTRY = build_registry()
    return _REGISTRY
