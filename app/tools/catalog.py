"""Explicit registration of workflow tools.

Future domain tools register the same way via ToolRegistry without changing
ToolExecutor.
"""

from __future__ import annotations

from app.tools.implementations.employee import GetEmployeeTool, GetLeaveBalanceTool
from app.tools.implementations.leave import CalculateLeaveImpactTool, UpdateLeaveBalanceTool
from app.tools.implementations.notification import NotifyEmployeeTool
from app.tools.implementations.onboarding import (
    CreateOnboardingTaskTool,
    GetEmployeeDocumentsTool,
    GetOnboardingPolicyTool,
    ListOnboardingTasksTool,
    RequestEquipmentTool,
    RequestSystemAccessTool,
    UpdateOnboardingStatusTool,
    ValidateOnboardingPolicyTool,
    VerifyEmployeeDocumentsTool,
)
from app.tools.implementations.policy import GetLeavePolicyTool, ValidateLeavePolicyTool
from app.tools.implementations.recruitment import (
    CalculateCandidateScoreTool,
    GetCandidateTool,
    GetJobTool,
    NotifyCandidateTool,
    NotifyRecruiterTool,
    ScheduleInterviewTool,
    SearchCandidatesTool,
    SearchJobsTool,
    ShortlistCandidateTool,
    ValidateRecruitmentPolicyTool,
)
from app.tools.registry import ToolRegistry

_REGISTRY: ToolRegistry | None = None


def build_registry() -> ToolRegistry:
    """Create a registry with leave, recruitment, and onboarding tools."""

    registry = ToolRegistry()
    registry.register(GetEmployeeTool())
    registry.register(GetLeaveBalanceTool())
    registry.register(GetLeavePolicyTool())
    registry.register(ValidateLeavePolicyTool())
    registry.register(CalculateLeaveImpactTool())
    registry.register(UpdateLeaveBalanceTool())
    registry.register(NotifyEmployeeTool())
    registry.register(GetJobTool())
    registry.register(SearchJobsTool())
    registry.register(SearchCandidatesTool())
    registry.register(GetCandidateTool())
    registry.register(CalculateCandidateScoreTool())
    registry.register(ValidateRecruitmentPolicyTool())
    registry.register(ShortlistCandidateTool())
    registry.register(ScheduleInterviewTool())
    registry.register(NotifyCandidateTool())
    registry.register(NotifyRecruiterTool())
    registry.register(GetEmployeeDocumentsTool())
    registry.register(VerifyEmployeeDocumentsTool())
    registry.register(GetOnboardingPolicyTool())
    registry.register(ValidateOnboardingPolicyTool())
    registry.register(CreateOnboardingTaskTool())
    registry.register(ListOnboardingTasksTool())
    registry.register(RequestEquipmentTool())
    registry.register(RequestSystemAccessTool())
    registry.register(UpdateOnboardingStatusTool())
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
