"""Attendance domain tools. Agents never access attendance JSON directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.attendance_store import get_attendance_store
from app.services.errors import SimulatedServiceError
from app.services.hr_store import get_hr_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import from_service_error
from app.tools.idempotency import build_idempotency_key


class GetAttendanceRecordsInput(BaseModel):
    employee_id: str = Field(min_length=1)
    start_date: str = Field(min_length=1)
    end_date: str = Field(min_length=1)
    organization_id: str = ""


class CalculateAttendanceSummaryInput(BaseModel):
    employee_id: str = ""
    start_date: str = Field(min_length=1)
    end_date: str = Field(min_length=1)
    records: list[dict[str, Any]] = Field(default_factory=list)
    organization_id: str = ""


class AttendancePolicyLookupInput(BaseModel):
    organization_id: str = ""


class ValidateAttendancePolicyInput(BaseModel):
    employee: dict[str, Any]
    attendance_summary: dict[str, Any]
    organization_id: str = ""


class FindAttendanceIssuesInput(BaseModel):
    start_date: str = Field(min_length=1)
    end_date: str = Field(min_length=1)
    department: str = ""
    organization_id: str = ""


class CreateAttendanceReviewInput(BaseModel):
    employee_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    severity: str = "warning"
    workflow_id: str = ""
    assignee: str = ""
    organization_id: str = ""


class UpdateAttendanceStatusInput(BaseModel):
    employee_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class SendAttendanceWarningInput(BaseModel):
    employee_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class GetAttendanceRecordsTool(BaseTool):
    spec = ToolSpec(
        name="get_attendance_records",
        description="Retrieve attendance records for an employee and date range.",
        category="attendance",
        capability="attendance.records.get",
        side_effect="read",
        allowed_agents=["attendance_research", "attendance_analysis", "service_research"],
        retryable=True,
        max_retries=2,
    )
    input_model = GetAttendanceRecordsInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = GetAttendanceRecordsInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            records = get_attendance_store().get_records(
                payload.employee_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "employee_id": payload.employee_id.upper(),
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "records": records,
            "count": len(records),
            "source": "simulated_attendance_store",
        }


class CalculateAttendanceSummaryTool(BaseTool):
    spec = ToolSpec(
        name="calculate_attendance_summary",
        description="Calculate structured attendance metrics from records.",
        category="attendance",
        capability="attendance.summary.calculate",
        side_effect="read",
        allowed_agents=["attendance_analysis", "attendance_research", "service_research"],
        retryable=True,
        max_retries=2,
    )
    input_model = CalculateAttendanceSummaryInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CalculateAttendanceSummaryInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        store = get_attendance_store()
        try:
            records = list(payload.records)
            if not records and payload.employee_id:
                records = store.get_records(
                    payload.employee_id,
                    start_date=payload.start_date,
                    end_date=payload.end_date,
                    organization_id=org,
                )
            return store.calculate_summary(
                records,
                start_date=payload.start_date,
                end_date=payload.end_date,
                employee_id=payload.employee_id,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class GetAttendancePolicyTool(BaseTool):
    spec = ToolSpec(
        name="get_attendance_policy",
        description="Retrieve the structured attendance policy.",
        category="attendance",
        capability="attendance.policy.lookup",
        side_effect="read",
        allowed_agents=["attendance_policy"],
    )
    input_model = AttendancePolicyLookupInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = AttendancePolicyLookupInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_attendance_store().get_policy(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ValidateAttendancePolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_attendance_policy",
        description="Validate attendance summary against structured policy.",
        category="attendance",
        capability="attendance.policy.validate",
        side_effect="read",
        allowed_agents=["attendance_policy"],
    )
    input_model = ValidateAttendancePolicyInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidateAttendancePolicyInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_attendance_store().validate_attendance_policy(
                employee=payload.employee,
                attendance_summary=payload.attendance_summary,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class FindAttendanceIssuesTool(BaseTool):
    spec = ToolSpec(
        name="find_attendance_issues",
        description="Find employees with attendance warnings or escalations.",
        category="attendance",
        capability="attendance.issues.find",
        side_effect="read",
        allowed_agents=["attendance_research", "attendance_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = FindAttendanceIssuesInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = FindAttendanceIssuesInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            directory = get_hr_store().list_employees(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        try:
            findings = get_attendance_store().find_employees_with_issues(
                start_date=payload.start_date,
                end_date=payload.end_date,
                department=payload.department or None,
                organization_id=org,
                employee_directory=directory,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "department": payload.department or None,
            "findings": findings,
            "count": len(findings),
            "source": "simulated_attendance_store",
        }


class CreateAttendanceReviewTool(BaseTool):
    spec = ToolSpec(
        name="create_attendance_review",
        description="Create an HR/manager attendance review (idempotent write).",
        category="attendance",
        capability="attendance.review.create",
        side_effect="write",
        allowed_agents=["attendance_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateAttendanceReviewInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateAttendanceReviewInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_attendance_store().create_review(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                reason=payload.reason,
                severity=payload.severity,
                assignee=payload.assignee,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class UpdateAttendanceStatusTool(BaseTool):
    spec = ToolSpec(
        name="update_attendance_status",
        description="Update attendance review status (idempotent write).",
        category="attendance",
        capability="attendance.status.update",
        side_effect="write",
        allowed_agents=["attendance_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = UpdateAttendanceStatusInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = UpdateAttendanceStatusInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_attendance_store().update_status(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                status=payload.status,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class SendAttendanceWarningTool(BaseTool):
    """Thin wrapper that records a warning send via the notification service."""

    spec = ToolSpec(
        name="send_attendance_warning",
        description="Send an attendance warning notification to an employee.",
        category="attendance",
        capability="attendance.warning.send",
        side_effect="write",
        allowed_agents=["attendance_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = SendAttendanceWarningInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        from app.services.notifications import get_notification_service

        payload = SendAttendanceWarningInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            record = get_notification_service().send(
                employee_id=payload.employee_id,
                message=payload.message,
                workflow_id=workflow_id,
                organization_id=org,
                idempotency_key=build_idempotency_key(
                    capability="attendance.warning.send",
                    workflow_id=workflow_id,
                    organization_id=org,
                    employee_id=payload.employee_id,
                    channel="attendance_warning",
                ),
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            **record,
            "warning_type": "attendance",
            "source": record.get("source") or "simulated_notification_service",
        }
