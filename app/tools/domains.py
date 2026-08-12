"""Planned HR tool domains and capabilities.

These entries document how future workflows will register tools without changing
the ToolExecutor. None of these tools are implemented in Module 2.
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
    # Onboarding
    {"category": "onboarding", "capability": "document.verify", "name": "verify_document", "side_effect": "read"},
    {"category": "onboarding", "capability": "task.create", "name": "create_onboarding_task", "side_effect": "write"},
    {"category": "onboarding", "capability": "equipment.request", "name": "request_equipment", "side_effect": "write"},
    {"category": "onboarding", "capability": "access.request", "name": "request_access", "side_effect": "write"},
    # Attendance
    {"category": "attendance", "capability": "attendance.lookup", "name": "get_attendance", "side_effect": "read"},
    {"category": "attendance", "capability": "absence.calculate", "name": "calculate_absence", "side_effect": "read"},
    {"category": "attendance", "capability": "attendance.pattern", "name": "detect_attendance_pattern", "side_effect": "read"},
    # Performance
    {"category": "performance", "capability": "performance.lookup", "name": "get_performance", "side_effect": "read"},
    {"category": "performance", "capability": "goals.lookup", "name": "get_goals", "side_effect": "read"},
    {"category": "performance", "capability": "development.plan.create", "name": "create_development_plan", "side_effect": "write"},
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
