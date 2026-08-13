"""Planned HR tool domains and capabilities.

These entries document how future workflows will register tools without changing
the ToolExecutor. Recruitment, onboarding, attendance, and performance tools are
implemented; remaining domains (training, offboarding) are documentation-only.
"""

from __future__ import annotations

from typing import TypedDict


class PlannedCapability(TypedDict):
    category: str
    capability: str
    name: str
    side_effect: str


PLANNED_TOOL_CAPABILITIES: list[PlannedCapability] = [
    # Recruitment
    {"category": "recruitment", "capability": "job.search", "name": "search_jobs", "side_effect": "read"},
    {"category": "recruitment", "capability": "candidate.search", "name": "search_candidates", "side_effect": "read"},
    {"category": "recruitment", "capability": "candidate.lookup", "name": "get_candidate", "side_effect": "read"},
    {"category": "recruitment", "capability": "candidate.score", "name": "score_candidate", "side_effect": "read"},
    {"category": "recruitment", "capability": "interview.schedule", "name": "schedule_interview", "side_effect": "write"},
    # Onboarding (early planning names; implemented tools use verify_employee_documents /
    # create_onboarding_task / request_equipment / request_system_access)
    {"category": "onboarding", "capability": "document.verify", "name": "verify_document", "side_effect": "read"},
    {"category": "onboarding", "capability": "task.create", "name": "create_onboarding_task_plan", "side_effect": "write"},
    {"category": "onboarding", "capability": "equipment.request", "name": "request_equipment_kit", "side_effect": "write"},
    {"category": "onboarding", "capability": "access.request", "name": "request_access_bundle", "side_effect": "write"},
    # Attendance
    {"category": "attendance", "capability": "attendance.records.get", "name": "get_attendance_records", "side_effect": "read"},
    {"category": "attendance", "capability": "attendance.summary.calculate", "name": "calculate_attendance_summary", "side_effect": "read"},
    {"category": "attendance", "capability": "attendance.policy.lookup", "name": "get_attendance_policy", "side_effect": "read"},
    {"category": "attendance", "capability": "attendance.policy.validate", "name": "validate_attendance_policy", "side_effect": "read"},
    {"category": "attendance", "capability": "attendance.issues.find", "name": "find_attendance_issues", "side_effect": "read"},
    {"category": "attendance", "capability": "attendance.review.create", "name": "create_attendance_review", "side_effect": "write"},
    {"category": "attendance", "capability": "attendance.warning.send", "name": "send_attendance_warning", "side_effect": "write"},
    {"category": "attendance", "capability": "attendance.status.update", "name": "update_attendance_status", "side_effect": "write"},
    # Performance
    {"category": "performance", "capability": "performance.records.get", "name": "get_performance_records", "side_effect": "read"},
    {"category": "performance", "capability": "performance.goals.get", "name": "get_performance_goals", "side_effect": "read"},
    {"category": "performance", "capability": "performance.summary.calculate", "name": "calculate_performance_summary", "side_effect": "read"},
    {"category": "performance", "capability": "performance.policy.lookup", "name": "get_performance_policy", "side_effect": "read"},
    {"category": "performance", "capability": "performance.policy.validate", "name": "validate_performance_policy", "side_effect": "read"},
    {"category": "performance", "capability": "performance.support.find", "name": "find_performance_support", "side_effect": "read"},
    {"category": "performance", "capability": "performance.review.create", "name": "create_performance_review", "side_effect": "write"},
    {"category": "performance", "capability": "performance.improvement_plan.create", "name": "create_improvement_plan", "side_effect": "write"},
    {"category": "performance", "capability": "performance.status.update", "name": "update_performance_status", "side_effect": "write"},
    # Training
    {"category": "training", "capability": "training.search", "name": "search_training", "side_effect": "read"},
    {"category": "training", "capability": "training.assign", "name": "assign_training", "side_effect": "write"},
    {"category": "training", "capability": "training.track", "name": "track_training", "side_effect": "read"},
    # Offboarding
    {"category": "offboarding", "capability": "resignation.lookup", "name": "get_resignation", "side_effect": "read"},
    {"category": "offboarding", "capability": "notice.validate", "name": "validate_notice_period", "side_effect": "read"},
    {"category": "offboarding", "capability": "clearance.create", "name": "create_clearance", "side_effect": "write"},
    {"category": "offboarding", "capability": "asset.return.request", "name": "request_asset_return", "side_effect": "write"},
    {"category": "offboarding", "capability": "access.revoke", "name": "revoke_access", "side_effect": "write"},
    # Notification
    {"category": "notification", "capability": "notification.email", "name": "send_email", "side_effect": "write"},
    {"category": "notification", "capability": "notification.in_app", "name": "send_in_app_notification", "side_effect": "write"},
    {"category": "notification", "capability": "notification.manager", "name": "send_manager_notification", "side_effect": "write"},
]


def planned_capabilities_for_category(category: str) -> list[PlannedCapability]:
    return [item for item in PLANNED_TOOL_CAPABILITIES if item["category"] == category]
