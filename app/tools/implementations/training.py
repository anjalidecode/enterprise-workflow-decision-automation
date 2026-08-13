"""Training domain tools. Agents never access training JSON directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.training_store import get_training_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import ToolNotFoundError, from_service_error


class TrainingHistoryInput(BaseModel):
    employee_id: str = Field(min_length=1)
    organization_id: str = ""


class TrainingCatalogSearchInput(BaseModel):
    organization_id: str = ""
    skill: str = ""
    query: str = ""
    level: str = ""


class TrainingCourseGetInput(BaseModel):
    course_id: str = Field(min_length=1)
    organization_id: str = ""


class SkillGapCalculateInput(BaseModel):
    employee_id: str = ""
    organization_id: str = ""
    employee_skills: list[dict[str, Any] | str] = Field(default_factory=list)
    role_requirements: list[dict[str, Any] | str] = Field(default_factory=list)
    performance_context: dict[str, Any] = Field(default_factory=dict)


class TrainingPolicyLookupInput(BaseModel):
    organization_id: str = ""


class ValidateTrainingPolicyInput(BaseModel):
    employee: dict[str, Any]
    course: dict[str, Any] | None = None
    courses: list[dict[str, Any]] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)
    organization_id: str = ""
    employee_skills: list[dict[str, Any] | str] = Field(default_factory=list)
    estimated_annual_spend: float | None = None


class CreateTrainingPlanInput(BaseModel):
    employee_id: str = Field(min_length=1)
    course_ids: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    reason: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class CreateTrainingEnrollmentInput(BaseModel):
    employee_id: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    reason: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class UpdateTrainingStatusInput(BaseModel):
    employee_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    course_id: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class GetTrainingHistoryTool(BaseTool):
    spec = ToolSpec(
        name="get_training_history",
        description="Retrieve previous training records and skill profile for an employee.",
        category="training",
        capability="training.history.get",
        side_effect="read",
        allowed_agents=["training_research", "skill_gap_analysis", "service_research"],
        retryable=True,
        max_retries=2,
    )
    input_model = TrainingHistoryInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = TrainingHistoryInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        store = get_training_store()
        try:
            history = store.get_history(payload.employee_id, organization_id=org)
            profile = store.get_skills_profile(payload.employee_id, organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "employee_id": payload.employee_id.upper(),
            "history": history,
            "count": len(history),
            "skills": list(profile.get("skills") or []),
            "role_requirements": list(profile.get("role_requirements") or []),
            "role": profile.get("role"),
            "source": "simulated_training_store",
        }


class SearchTrainingCatalogTool(BaseTool):
    spec = ToolSpec(
        name="search_training_catalog",
        description="Search available training programs by skill, query, or level.",
        category="training",
        capability="training.catalog.search",
        side_effect="read",
        allowed_agents=["training_catalog_research", "training_analysis", "service_research"],
        retryable=True,
        max_retries=2,
    )
    input_model = TrainingCatalogSearchInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = TrainingCatalogSearchInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            courses = get_training_store().search_catalog(
                organization_id=org,
                skill=payload.skill,
                query=payload.query,
                level=payload.level,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "courses": courses,
            "count": len(courses),
            "skill": payload.skill or None,
            "query": payload.query or None,
            "level": payload.level or None,
            "source": "simulated_training_store",
        }


class GetTrainingCourseTool(BaseTool):
    spec = ToolSpec(
        name="get_training_course",
        description="Retrieve details for a single training course.",
        category="training",
        capability="training.course.get",
        side_effect="read",
        allowed_agents=["training_catalog_research", "training_analysis", "training_policy"],
        retryable=True,
        max_retries=2,
    )
    input_model = TrainingCourseGetInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = TrainingCourseGetInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            course = get_training_store().get_course(payload.course_id, organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        if course is None:
            raise ToolNotFoundError(f"Course {payload.course_id} not found.")
        return {**course, "source": "simulated_training_store"}


class CalculateSkillGapTool(BaseTool):
    spec = ToolSpec(
        name="calculate_skill_gap",
        description="Calculate structured skill gaps from skills, role requirements, and performance context.",
        category="training",
        capability="training.skill_gap.calculate",
        side_effect="read",
        allowed_agents=["skill_gap_analysis", "training_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = SkillGapCalculateInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = SkillGapCalculateInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_training_store().calculate_skill_gaps(
                employee_skills=payload.employee_skills,
                role_requirements=payload.role_requirements,
                performance_context=payload.performance_context,
                employee_id=payload.employee_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class GetTrainingPolicyTool(BaseTool):
    spec = ToolSpec(
        name="get_training_policy",
        description="Retrieve the structured training policy.",
        category="training",
        capability="training.policy.lookup",
        side_effect="read",
        allowed_agents=["training_policy"],
    )
    input_model = TrainingPolicyLookupInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = TrainingPolicyLookupInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_training_store().get_policy(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ValidateTrainingPolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_training_policy",
        description="Validate employee/course eligibility against structured training policy.",
        category="training",
        capability="training.policy.validate",
        side_effect="read",
        allowed_agents=["training_policy"],
    )
    input_model = ValidateTrainingPolicyInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidateTrainingPolicyInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_training_store().validate_training_policy(
                employee=payload.employee,
                course=payload.course,
                courses=payload.courses,
                prerequisites=payload.prerequisites or None,
                policy=payload.policy or None,
                organization_id=org,
                employee_skills=payload.employee_skills,
                estimated_annual_spend=payload.estimated_annual_spend,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateTrainingPlanTool(BaseTool):
    spec = ToolSpec(
        name="create_training_plan",
        description="Create a training plan for an employee (idempotent write).",
        category="training",
        capability="training.plan.create",
        side_effect="write",
        allowed_agents=["training_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateTrainingPlanInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateTrainingPlanInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_training_store().create_plan(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                course_ids=payload.course_ids,
                skill_gaps=payload.skill_gaps,
                reason=payload.reason,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateTrainingEnrollmentTool(BaseTool):
    spec = ToolSpec(
        name="create_training_enrollment",
        description="Enroll an employee in a training course (idempotent write).",
        category="training",
        capability="training.enrollment.create",
        side_effect="write",
        allowed_agents=["training_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateTrainingEnrollmentInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateTrainingEnrollmentInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_training_store().create_enrollment(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                course_id=payload.course_id,
                organization_id=org,
                reason=payload.reason,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class UpdateTrainingStatusTool(BaseTool):
    spec = ToolSpec(
        name="update_training_status",
        description="Update training workflow/enrollment status (idempotent write).",
        category="training",
        capability="training.status.update",
        side_effect="write",
        allowed_agents=["training_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = UpdateTrainingStatusInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = UpdateTrainingStatusInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_training_store().update_status(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                status=payload.status,
                course_id=payload.course_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
