"""Explicit registration of workflow tools.

Future domain tools register the same way via ToolRegistry without changing
ToolExecutor.
"""

from __future__ import annotations

from app.tools.implementations.attendance import (
    CalculateAttendanceSummaryTool,
    CreateAttendanceReviewTool,
    FindAttendanceIssuesTool,
    GetAttendancePolicyTool,
    GetAttendanceRecordsTool,
    SendAttendanceWarningTool,
    UpdateAttendanceStatusTool,
    ValidateAttendancePolicyTool,
)
from app.tools.implementations.performance import (
    CalculatePerformanceSummaryTool,
    CreateImprovementPlanTool,
    CreatePerformanceReviewTool,
    FindPerformanceSupportTool,
    GetPerformanceGoalsTool,
    GetPerformancePolicyTool,
    GetPerformanceRecordsTool,
    UpdatePerformanceStatusTool,
    ValidatePerformancePolicyTool,
)
from app.tools.implementations.training import (
    CalculateSkillGapTool,
    CreateTrainingEnrollmentTool,
    CreateTrainingPlanTool,
    GetTrainingCourseTool,
    GetTrainingHistoryTool,
    GetTrainingPolicyTool,
    SearchTrainingCatalogTool,
    UpdateTrainingStatusTool,
    ValidateTrainingPolicyTool,
)
from app.tools.implementations.offboarding import (
    CreateAccessRevokeRequestTool,
    CreateOffboardingHandoverTool,
    CreateOffboardingTaskTool,
    GetOffboardingChecklistTool,
    GetOffboardingExitTool,
    GetOffboardingPolicyTool,
    ListOffboardingAssetsTool,
    RequestAssetReturnTool,
    ScheduleExitInterviewTool,
    UpdateOffboardingStatusTool,
    ValidateOffboardingPolicyTool,
)
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
    """Create a registry with leave through offboarding tools."""

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
    registry.register(GetAttendanceRecordsTool())
    registry.register(CalculateAttendanceSummaryTool())
    registry.register(GetAttendancePolicyTool())
    registry.register(ValidateAttendancePolicyTool())
    registry.register(FindAttendanceIssuesTool())
    registry.register(CreateAttendanceReviewTool())
    registry.register(SendAttendanceWarningTool())
    registry.register(UpdateAttendanceStatusTool())
    registry.register(GetPerformanceRecordsTool())
    registry.register(GetPerformanceGoalsTool())
    registry.register(CalculatePerformanceSummaryTool())
    registry.register(GetPerformancePolicyTool())
    registry.register(ValidatePerformancePolicyTool())
    registry.register(FindPerformanceSupportTool())
    registry.register(CreatePerformanceReviewTool())
    registry.register(CreateImprovementPlanTool())
    registry.register(UpdatePerformanceStatusTool())
    registry.register(GetTrainingHistoryTool())
    registry.register(SearchTrainingCatalogTool())
    registry.register(GetTrainingCourseTool())
    registry.register(CalculateSkillGapTool())
    registry.register(GetTrainingPolicyTool())
    registry.register(ValidateTrainingPolicyTool())
    registry.register(CreateTrainingPlanTool())
    registry.register(CreateTrainingEnrollmentTool())
    registry.register(UpdateTrainingStatusTool())
    registry.register(GetOffboardingExitTool())
    registry.register(GetOffboardingPolicyTool())
    registry.register(ValidateOffboardingPolicyTool())
    registry.register(GetOffboardingChecklistTool())
    registry.register(CreateOffboardingTaskTool())
    registry.register(ListOffboardingAssetsTool())
    registry.register(RequestAssetReturnTool())
    registry.register(CreateOffboardingHandoverTool())
    registry.register(ScheduleExitInterviewTool())
    registry.register(CreateAccessRevokeRequestTool())
    registry.register(UpdateOffboardingStatusTool())
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
