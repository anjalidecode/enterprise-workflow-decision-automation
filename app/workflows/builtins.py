"""Builtin workflow registrations for the platform spine."""

from __future__ import annotations

from typing import Any

from app.workflows.attendance_workflow import (
    ATTENDANCE_AGENT_NODES,
    build_attendance_workflow,
    run_attendance_workflow,
)
from app.workflows.contracts import WorkflowSpec
from app.workflows.leave_workflow import (
    AGENT_NODES,
    build_leave_workflow,
    run_leave_workflow,
)
from app.workflows.onboarding_workflow import (
    ONBOARDING_AGENT_NODES,
    build_onboarding_workflow,
    run_onboarding_workflow,
)
from app.workflows.performance_workflow import (
    PERFORMANCE_AGENT_NODES,
    build_performance_workflow,
    run_performance_workflow,
)
from app.workflows.recruitment_workflow import (
    RECRUITMENT_AGENT_NODES,
    build_recruitment_workflow,
    run_recruitment_workflow,
)
from app.workflows.training_workflow import (
    TRAINING_AGENT_NODES,
    build_training_workflow,
    run_training_workflow,
)
from app.workflows.offboarding_workflow import (
    OFFBOARDING_AGENT_NODES,
    build_offboarding_workflow,
    run_offboarding_workflow,
)
from app.workflows.registry import WorkflowRegistry

LEAVE_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="leave_attendance",
    name="Leave & Attendance",
    description=(
        "Evaluate leave requests against employee records, leave balances, and "
        "structured leave policy. Supports approve, reject, and human approval paths."
    ),
    supported_request_hints=[
        "leave",
        "time off",
        "pto",
        "vacation",
        "annual leave",
        "sick leave",
    ],
    required_agents=list(AGENT_NODES),
    required_tool_capabilities=[
        "employee.lookup",
        "employee.leave_balance",
        "policy.lookup",
        "policy.validate_leave",
        "leave.impact",
        "leave.balance.update",
        "notification.send",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "leave_attendance",
    },
    entry_node="orchestrator",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)

RECRUITMENT_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="recruitment",
    name="Recruitment",
    description=(
        "Analyze a job requisition, score candidates, apply recruitment policy, "
        "and shortlist/interview with human approval for high-impact actions."
    ),
    supported_request_hints=[
        "recruit",
        "recruitment",
        "candidate",
        "candidates",
        "job opening",
        "hire",
        "shortlist",
        "interview",
        "python backend",
        "frontend developer",
    ],
    required_agents=list(RECRUITMENT_AGENT_NODES),
    required_tool_capabilities=[
        "job.lookup",
        "job.search",
        "candidate.search",
        "candidate.lookup",
        "candidate.score",
        "policy.validate_recruitment",
        "recruitment.shortlist",
        "interview.schedule",
        "notification.candidate",
        "notification.recruiter",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "recruitment",
    },
    entry_node="recruitment_planner",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)

ONBOARDING_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="onboarding",
    name="Employee Onboarding",
    description=(
        "Onboard a new employee by verifying documents, applying onboarding policy, "
        "creating tasks, requesting equipment and system access, with human approval "
        "for privileged access."
    ),
    supported_request_hints=[
        "onboarding",
        "onboard",
        "new employee",
        "new hire",
        "joining",
        "join",
        "start onboarding",
    ],
    required_agents=list(ONBOARDING_AGENT_NODES),
    required_tool_capabilities=[
        "employee.lookup",
        "employee.documents",
        "employee.document.verify",
        "onboarding.policy.lookup",
        "onboarding.policy.validate",
        "onboarding.task.create",
        "onboarding.task.list",
        "onboarding.equipment.request",
        "onboarding.access.request",
        "onboarding.status.update",
        "notification.send",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "onboarding",
    },
    entry_node="onboarding_planner",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)

ATTENDANCE_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="attendance",
    name="Attendance Decision & Automation",
    description=(
        "Analyze employee attendance records against structured attendance policy, "
        "detect irregularities, warnings, and escalations, and create review/"
        "notification actions with human approval for serious issues."
    ),
    supported_request_hints=[
        "attendance",
        "absent",
        "absence",
        "late",
        "lateness",
        "attendance record",
        "attendance report",
        "attendance issue",
        "present days",
    ],
    required_agents=list(ATTENDANCE_AGENT_NODES),
    required_tool_capabilities=[
        "employee.lookup",
        "attendance.records.get",
        "attendance.summary.calculate",
        "attendance.policy.lookup",
        "attendance.policy.validate",
        "attendance.issues.find",
        "attendance.review.create",
        "attendance.warning.send",
        "attendance.status.update",
        "notification.send",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "attendance",
    },
    entry_node="attendance_planner",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)

PERFORMANCE_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="performance",
    name="Employee Performance Management",
    description=(
        "Analyze employee performance against goals and KPIs, apply performance "
        "policy, and recommend review or improvement-plan actions with human "
        "approval for serious concerns."
    ),
    supported_request_hints=[
        "performance",
        "performance review",
        "appraisal",
        "appraisal review",
        "kpi",
        "goal",
        "performance report",
        "performance issue",
        "improvement plan",
        "performance support",
    ],
    required_agents=list(PERFORMANCE_AGENT_NODES),
    required_tool_capabilities=[
        "employee.lookup",
        "performance.records.get",
        "performance.goals.get",
        "performance.summary.calculate",
        "performance.policy.lookup",
        "performance.policy.validate",
        "performance.support.find",
        "performance.review.create",
        "performance.improvement_plan.create",
        "performance.status.update",
        "notification.send",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "performance",
    },
    entry_node="performance_planner",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)

TRAINING_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="training",
    name="Employee Training & Skill Development",
    description=(
        "Identify skill gaps, match training catalog courses, apply training "
        "policy, and enroll employees with human approval for high-cost courses."
    ),
    supported_request_hints=[
        "training",
        "course",
        "courses",
        "skill gap",
        "skill development",
        "upskilling",
        "reskilling",
        "learning",
        "training plan",
        "recommend training",
    ],
    required_agents=list(TRAINING_AGENT_NODES),
    required_tool_capabilities=[
        "employee.lookup",
        "training.history.get",
        "training.catalog.search",
        "training.course.get",
        "training.skill_gap.calculate",
        "training.policy.lookup",
        "training.policy.validate",
        "training.plan.create",
        "training.enrollment.create",
        "training.status.update",
        "notification.send",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "training",
    },
    entry_node="training_planner",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)

OFFBOARDING_WORKFLOW_SPEC = WorkflowSpec(
    workflow_type="offboarding",
    name="Employee Offboarding & Exit Management",
    description=(
        "Coordinate employee exit preparation including notice validation, exit "
        "checklist, asset return, knowledge handover, exit interview, and "
        "access-revocation requests with human approval for privileged actions."
    ),
    supported_request_hints=[
        "offboarding",
        "offboard",
        "resignation",
        "resign",
        "exit employee",
        "employee exit",
        "last working day",
        "exit process",
        "exit checklist",
        "offboarding process",
    ],
    required_agents=list(OFFBOARDING_AGENT_NODES),
    required_tool_capabilities=[
        "employee.lookup",
        "offboarding.exit.get",
        "offboarding.policy.lookup",
        "offboarding.policy.validate",
        "offboarding.checklist.get",
        "offboarding.task.create",
        "offboarding.asset.list",
        "offboarding.asset.return",
        "offboarding.handover.create",
        "offboarding.exit_interview.schedule",
        "offboarding.access.revoke_request",
        "offboarding.status.update",
        "notification.send",
    ],
    memory_profile={
        "short_term": True,
        "knowledge": True,
        "long_term": True,
        "knowledge_workflow_type": "offboarding",
    },
    entry_node="offboarding_planner",
    terminal_statuses=[
        "completed",
        "awaiting_human_approval",
        "validation_failed",
        "failed",
    ],
    approval_outcomes=["pending_approval", "escalate"],
    version="1.0",
)


def _leave_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "leave_attendance",
    **_: Any,
):
    return run_leave_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def _recruitment_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "recruitment",
    **_: Any,
):
    return run_recruitment_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def _onboarding_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "onboarding",
    **_: Any,
):
    return run_onboarding_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def _attendance_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "attendance",
    **_: Any,
):
    return run_attendance_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def _performance_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "performance",
    **_: Any,
):
    return run_performance_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def _training_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "training",
    **_: Any,
):
    return run_training_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def _offboarding_runner(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "offboarding",
    **_: Any,
):
    return run_offboarding_workflow(
        user_request,
        reset_runtime=reset_runtime,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type,
    )


def register_builtin_workflows(registry: WorkflowRegistry) -> None:
    """Register leave through offboarding workflows."""

    registry.register(
        LEAVE_WORKFLOW_SPEC,
        runner=_leave_runner,
        graph_factory=build_leave_workflow,
        validate_tools=True,
    )
    registry.register(
        RECRUITMENT_WORKFLOW_SPEC,
        runner=_recruitment_runner,
        graph_factory=build_recruitment_workflow,
        validate_tools=True,
    )
    registry.register(
        ONBOARDING_WORKFLOW_SPEC,
        runner=_onboarding_runner,
        graph_factory=build_onboarding_workflow,
        validate_tools=True,
    )
    registry.register(
        ATTENDANCE_WORKFLOW_SPEC,
        runner=_attendance_runner,
        graph_factory=build_attendance_workflow,
        validate_tools=True,
    )
    registry.register(
        PERFORMANCE_WORKFLOW_SPEC,
        runner=_performance_runner,
        graph_factory=build_performance_workflow,
        validate_tools=True,
    )
    registry.register(
        TRAINING_WORKFLOW_SPEC,
        runner=_training_runner,
        graph_factory=build_training_workflow,
        validate_tools=True,
    )
    registry.register(
        OFFBOARDING_WORKFLOW_SPEC,
        runner=_offboarding_runner,
        graph_factory=build_offboarding_workflow,
        validate_tools=True,
    )
