"""Recruitment domain tools. Agents never access recruitment JSON directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.notifications import get_notification_service
from app.services.recruitment_store import get_recruitment_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import from_service_error
from app.tools.idempotency import build_idempotency_key


class GetJobInput(BaseModel):
    job_id: str = Field(min_length=1)
    organization_id: str = ""


class SearchJobsInput(BaseModel):
    query: str = ""
    organization_id: str = ""
    status: str = "open"


class SearchCandidatesInput(BaseModel):
    organization_id: str = ""
    required_skills: list[str] = Field(default_factory=list)
    application_status: str = "active"


class GetCandidateInput(BaseModel):
    candidate_id: str = Field(min_length=1)
    organization_id: str = ""


class CalculateCandidateScoreInput(BaseModel):
    job: dict[str, Any]
    candidate: dict[str, Any]
    organization_id: str = ""


class ValidateRecruitmentPolicyInput(BaseModel):
    job: dict[str, Any]
    candidate: dict[str, Any]
    score_result: dict[str, Any]
    organization_id: str = ""


class ShortlistCandidateInput(BaseModel):
    job_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    workflow_id: str = ""
    score: float | None = None
    organization_id: str = ""


class ScheduleInterviewInput(BaseModel):
    job_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    workflow_id: str = ""
    slot: str = "next_business_day_10:00"
    organization_id: str = ""


class NotifyRecipientInput(BaseModel):
    recipient_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    workflow_id: str = ""


class GetJobTool(BaseTool):
    spec = ToolSpec(
        name="get_job",
        description="Retrieve a job requisition by id.",
        category="recruitment",
        capability="job.lookup",
        side_effect="read",
        allowed_agents=["job_research", "recruitment_planner"],
    )
    input_model = GetJobInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = GetJobInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            job = get_recruitment_store().get_job(payload.job_id, organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        if job is None:
            return {"found": False, "job_id": payload.job_id}
        return {"found": True, "job": job}


class SearchJobsTool(BaseTool):
    spec = ToolSpec(
        name="search_jobs",
        description="Search open jobs by query text.",
        category="recruitment",
        capability="job.search",
        side_effect="read",
        allowed_agents=["job_research", "recruitment_planner"],
    )
    input_model = SearchJobsInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = SearchJobsInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            jobs = get_recruitment_store().search_jobs(
                organization_id=org,
                query=payload.query,
                status=payload.status or None,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {"jobs": jobs, "count": len(jobs)}


class SearchCandidatesTool(BaseTool):
    spec = ToolSpec(
        name="search_candidates",
        description="Search active candidates for a job's criteria.",
        category="recruitment",
        capability="candidate.search",
        side_effect="read",
        allowed_agents=["candidate_research"],
    )
    input_model = SearchCandidatesInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = SearchCandidatesInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            candidates = get_recruitment_store().search_candidates(
                organization_id=org,
                required_skills=payload.required_skills,
                application_status=payload.application_status,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {"candidates": candidates, "count": len(candidates)}


class GetCandidateTool(BaseTool):
    spec = ToolSpec(
        name="get_candidate",
        description="Retrieve one candidate profile by id.",
        category="recruitment",
        capability="candidate.lookup",
        side_effect="read",
        allowed_agents=["candidate_research", "candidate_analysis"],
    )
    input_model = GetCandidateInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = GetCandidateInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            candidate = get_recruitment_store().get_candidate(
                payload.candidate_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        if candidate is None:
            return {"found": False, "candidate_id": payload.candidate_id}
        return {"found": True, "candidate": candidate}


class CalculateCandidateScoreTool(BaseTool):
    spec = ToolSpec(
        name="calculate_candidate_score",
        description="Deterministically score a candidate against a job.",
        category="recruitment",
        capability="candidate.score",
        side_effect="read",
        allowed_agents=["candidate_scoring"],
    )
    input_model = CalculateCandidateScoreInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CalculateCandidateScoreInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_recruitment_store().calculate_candidate_score(
                job=payload.job,
                candidate=payload.candidate,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ValidateRecruitmentPolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_recruitment_policy",
        description="Validate recruitment policy for a scored candidate.",
        category="recruitment",
        capability="policy.validate_recruitment",
        side_effect="read",
        allowed_agents=["recruitment_policy"],
    )
    input_model = ValidateRecruitmentPolicyInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidateRecruitmentPolicyInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_recruitment_store().validate_recruitment_policy(
                job=payload.job,
                candidate=payload.candidate,
                score_result=payload.score_result,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ShortlistCandidateTool(BaseTool):
    spec = ToolSpec(
        name="shortlist_candidate",
        description="Shortlist a candidate for a job (idempotent write).",
        category="recruitment",
        capability="recruitment.shortlist",
        side_effect="write",
        allowed_agents=["action", "recruitment_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = ShortlistCandidateInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ShortlistCandidateInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_recruitment_store().shortlist_candidate(
                workflow_id=workflow_id,
                job_id=payload.job_id,
                candidate_id=payload.candidate_id,
                organization_id=org,
                score=payload.score,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ScheduleInterviewTool(BaseTool):
    spec = ToolSpec(
        name="schedule_interview",
        description="Schedule an interview for a shortlisted candidate (idempotent).",
        category="recruitment",
        capability="interview.schedule",
        side_effect="write",
        allowed_agents=["action", "recruitment_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = ScheduleInterviewInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ScheduleInterviewInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_recruitment_store().schedule_interview(
                workflow_id=workflow_id,
                job_id=payload.job_id,
                candidate_id=payload.candidate_id,
                organization_id=org,
                slot=payload.slot,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class NotifyCandidateTool(BaseTool):
    spec = ToolSpec(
        name="notify_candidate",
        description="Notify a candidate via the simulated notification sink.",
        category="notification",
        capability="notification.candidate",
        side_effect="write",
        allowed_agents=["action", "recruitment_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = NotifyRecipientInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = NotifyRecipientInput.model_validate(inputs.model_dump())
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            record = get_notification_service().send(
                employee_id=payload.recipient_id,
                message=payload.message,
                workflow_id=workflow_id,
                organization_id=context.organization_id,
                idempotency_key=build_idempotency_key(
                    capability="notification.candidate",
                    workflow_id=workflow_id,
                    organization_id=context.organization_id,
                    recipient_id=payload.recipient_id,
                    channel="simulated_inbox",
                ),
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {**record, "recipient_id": payload.recipient_id, "recipient_type": "candidate"}


class NotifyRecruiterTool(BaseTool):
    spec = ToolSpec(
        name="notify_recruiter",
        description="Notify a recruiter via the simulated notification sink.",
        category="notification",
        capability="notification.recruiter",
        side_effect="write",
        allowed_agents=["action", "recruitment_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = NotifyRecipientInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = NotifyRecipientInput.model_validate(inputs.model_dump())
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            record = get_notification_service().send(
                employee_id=payload.recipient_id,
                message=payload.message,
                workflow_id=workflow_id,
                organization_id=context.organization_id,
                idempotency_key=build_idempotency_key(
                    capability="notification.recruiter",
                    workflow_id=workflow_id,
                    organization_id=context.organization_id,
                    recipient_id=payload.recipient_id,
                    channel="simulated_inbox",
                ),
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {**record, "recipient_id": payload.recipient_id, "recipient_type": "recruiter"}
