"""Performance domain tools. Agents never access performance JSON directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.hr_store import get_hr_store
from app.services.performance_store import get_performance_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import from_service_error


class GetPerformanceRecordsInput(BaseModel):
    employee_id: str = Field(min_length=1)
    review_period: str = Field(min_length=1)
    organization_id: str = ""


class GetPerformanceGoalsInput(BaseModel):
    employee_id: str = Field(min_length=1)
    review_period: str = Field(min_length=1)
    organization_id: str = ""


class CalculatePerformanceSummaryInput(BaseModel):
    employee_id: str = ""
    review_period: str = ""
    records: list[dict[str, Any]] = Field(default_factory=list)
    goals: list[dict[str, Any]] = Field(default_factory=list)
    organization_id: str = ""


class PerformancePolicyLookupInput(BaseModel):
    organization_id: str = ""


class ValidatePerformancePolicyInput(BaseModel):
    employee: dict[str, Any]
    performance_summary: dict[str, Any]
    organization_id: str = ""


class FindPerformanceSupportInput(BaseModel):
    review_period: str = Field(min_length=1)
    organization_id: str = ""


class CreatePerformanceReviewInput(BaseModel):
    employee_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    severity: str = "development"
    workflow_id: str = ""
    assignee: str = ""
    organization_id: str = ""
    review_period: str = ""


class CreateImprovementPlanInput(BaseModel):
    employee_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    plan_type: str = "performance_improvement"
    focus_areas: list[str] = Field(default_factory=list)
    workflow_id: str = ""
    organization_id: str = ""
    review_period: str = ""


class UpdatePerformanceStatusInput(BaseModel):
    employee_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""
    review_period: str = ""


class GetPerformanceRecordsTool(BaseTool):
    spec = ToolSpec(
        name="get_performance_records",
        description="Retrieve performance records for an employee and review period.",
        category="performance",
        capability="performance.records.get",
        side_effect="read",
        allowed_agents=["performance_research", "goal_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = GetPerformanceRecordsInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = GetPerformanceRecordsInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            records = get_performance_store().get_records(
                payload.employee_id,
                review_period=payload.review_period,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "employee_id": payload.employee_id.upper(),
            "review_period": payload.review_period,
            "records": records,
            "count": len(records),
            "source": "simulated_performance_store",
        }


class GetPerformanceGoalsTool(BaseTool):
    spec = ToolSpec(
        name="get_performance_goals",
        description="Retrieve goals and KPIs for an employee and review period.",
        category="performance",
        capability="performance.goals.get",
        side_effect="read",
        allowed_agents=["performance_research", "goal_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = GetPerformanceGoalsInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = GetPerformanceGoalsInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            goals = get_performance_store().get_goals(
                payload.employee_id,
                review_period=payload.review_period,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "employee_id": payload.employee_id.upper(),
            "review_period": payload.review_period,
            "goals": goals,
            "count": len(goals),
            "source": "simulated_performance_store",
        }


class CalculatePerformanceSummaryTool(BaseTool):
    spec = ToolSpec(
        name="calculate_performance_summary",
        description="Calculate structured performance metrics and goal achievement.",
        category="performance",
        capability="performance.summary.calculate",
        side_effect="read",
        allowed_agents=["goal_analysis", "performance_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = CalculatePerformanceSummaryInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CalculatePerformanceSummaryInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        store = get_performance_store()
        try:
            records = list(payload.records)
            goals = list(payload.goals)
            if payload.employee_id and payload.review_period:
                if not records:
                    records = store.get_records(
                        payload.employee_id,
                        review_period=payload.review_period,
                        organization_id=org,
                    )
                if not goals:
                    goals = store.get_goals(
                        payload.employee_id,
                        review_period=payload.review_period,
                        organization_id=org,
                    )
            return store.calculate_summary(
                records,
                goals,
                employee_id=payload.employee_id,
                review_period=payload.review_period,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class GetPerformancePolicyTool(BaseTool):
    spec = ToolSpec(
        name="get_performance_policy",
        description="Retrieve the structured performance management policy.",
        category="performance",
        capability="performance.policy.lookup",
        side_effect="read",
        allowed_agents=["performance_policy"],
    )
    input_model = PerformancePolicyLookupInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = PerformancePolicyLookupInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_performance_store().get_policy(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ValidatePerformancePolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_performance_policy",
        description="Validate performance summary against structured policy.",
        category="performance",
        capability="performance.policy.validate",
        side_effect="read",
        allowed_agents=["performance_policy"],
    )
    input_model = ValidatePerformancePolicyInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidatePerformancePolicyInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_performance_store().validate_performance_policy(
                employee=payload.employee,
                performance_summary=payload.performance_summary,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class FindPerformanceSupportTool(BaseTool):
    spec = ToolSpec(
        name="find_performance_support",
        description="Find employees who need performance support or review.",
        category="performance",
        capability="performance.support.find",
        side_effect="read",
        allowed_agents=["performance_research", "performance_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = FindPerformanceSupportInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = FindPerformanceSupportInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            directory = get_hr_store().list_employees(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        try:
            findings = get_performance_store().find_employees_needing_support(
                review_period=payload.review_period,
                organization_id=org,
                employee_directory=directory,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "review_period": payload.review_period,
            "findings": findings,
            "count": len(findings),
            "source": "simulated_performance_store",
        }


class CreatePerformanceReviewTool(BaseTool):
    spec = ToolSpec(
        name="create_performance_review",
        description="Create a manager/HR performance review task (idempotent write).",
        category="performance",
        capability="performance.review.create",
        side_effect="write",
        allowed_agents=["performance_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreatePerformanceReviewInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreatePerformanceReviewInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_performance_store().create_review(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                reason=payload.reason,
                severity=payload.severity,
                assignee=payload.assignee,
                organization_id=org,
                review_period=payload.review_period,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateImprovementPlanTool(BaseTool):
    spec = ToolSpec(
        name="create_improvement_plan",
        description="Create a recommended development or improvement plan task (not disciplinary).",
        category="performance",
        capability="performance.improvement_plan.create",
        side_effect="write",
        allowed_agents=["performance_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateImprovementPlanInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateImprovementPlanInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_performance_store().create_improvement_plan(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                reason=payload.reason,
                plan_type=payload.plan_type,
                focus_areas=payload.focus_areas,
                organization_id=org,
                review_period=payload.review_period,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class UpdatePerformanceStatusTool(BaseTool):
    spec = ToolSpec(
        name="update_performance_status",
        description="Update performance review workflow status (idempotent write).",
        category="performance",
        capability="performance.status.update",
        side_effect="write",
        allowed_agents=["performance_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = UpdatePerformanceStatusInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = UpdatePerformanceStatusInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_performance_store().update_status(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                status=payload.status,
                organization_id=org,
                review_period=payload.review_period,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
