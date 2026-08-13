"""Offboarding domain tools. Agents never access offboarding JSON directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.offboarding_store import get_offboarding_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import ToolNotFoundError, from_service_error


class OffboardingExitGetInput(BaseModel):
    employee_id: str = Field(min_length=1)
    organization_id: str = ""


class OffboardingPolicyLookupInput(BaseModel):
    organization_id: str = ""


class ValidateOffboardingPolicyInput(BaseModel):
    employee: dict[str, Any]
    exit_record: dict[str, Any] = Field(default_factory=dict)
    checklist: dict[str, Any] = Field(default_factory=dict)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    handover: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    organization_id: str = ""


class OffboardingChecklistGetInput(BaseModel):
    employee_id: str = Field(min_length=1)
    exit_record: dict[str, Any] = Field(default_factory=dict)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    handover: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    workflow_id: str = ""
    organization_id: str = ""


class CreateOffboardingTaskInput(BaseModel):
    employee_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    details: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class ListOffboardingAssetsInput(BaseModel):
    employee_id: str = Field(min_length=1)
    organization_id: str = ""


class RequestAssetReturnInput(BaseModel):
    employee_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class CreateOffboardingHandoverInput(BaseModel):
    employee_id: str = Field(min_length=1)
    projects: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    knowledge_areas: list[str] = Field(default_factory=list)
    manager: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class ScheduleExitInterviewInput(BaseModel):
    employee_id: str = Field(min_length=1)
    scheduled_for: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class CreateAccessRevokeRequestInput(BaseModel):
    employee_id: str = Field(min_length=1)
    systems: list[str] = Field(default_factory=list)
    privileged: bool = False
    workflow_id: str = ""
    organization_id: str = ""


class UpdateOffboardingStatusInput(BaseModel):
    employee_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class GetOffboardingExitTool(BaseTool):
    spec = ToolSpec(
        name="get_offboarding_exit",
        description="Retrieve resignation/exit details for an employee.",
        category="offboarding",
        capability="offboarding.exit.get",
        side_effect="read",
        allowed_agents=["exit_details_research", "offboarding_analysis", "checklist_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = OffboardingExitGetInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = OffboardingExitGetInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        store = get_offboarding_store()
        try:
            record = store.get_exit(payload.employee_id, organization_id=org)
            handover = store.get_handover(payload.employee_id, organization_id=org) or {}
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        if record is None:
            raise ToolNotFoundError(f"Exit record for {payload.employee_id} not found.")
        return {
            **record,
            "handover": handover,
            "source": "simulated_offboarding_store",
        }


class GetOffboardingPolicyTool(BaseTool):
    spec = ToolSpec(
        name="get_offboarding_policy",
        description="Retrieve the structured offboarding policy.",
        category="offboarding",
        capability="offboarding.policy.lookup",
        side_effect="read",
        allowed_agents=["offboarding_policy"],
    )
    input_model = OffboardingPolicyLookupInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = OffboardingPolicyLookupInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_offboarding_store().get_policy(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ValidateOffboardingPolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_offboarding_policy",
        description="Validate notice period, approvals, and exit requirements against policy.",
        category="offboarding",
        capability="offboarding.policy.validate",
        side_effect="read",
        allowed_agents=["offboarding_policy"],
    )
    input_model = ValidateOffboardingPolicyInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidateOffboardingPolicyInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_offboarding_store().validate_offboarding_policy(
                employee=payload.employee,
                exit_record=payload.exit_record or None,
                checklist=payload.checklist or None,
                assets=payload.assets or None,
                handover=payload.handover or None,
                policy=payload.policy or None,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class GetOffboardingChecklistTool(BaseTool):
    spec = ToolSpec(
        name="get_offboarding_checklist",
        description="Retrieve or build structured exit checklist state.",
        category="offboarding",
        capability="offboarding.checklist.get",
        side_effect="read",
        allowed_agents=["checklist_analysis", "offboarding_analysis", "offboarding_policy"],
        retryable=True,
        max_retries=2,
    )
    input_model = OffboardingChecklistGetInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = OffboardingChecklistGetInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_offboarding_store().build_checklist(
                employee_id=payload.employee_id,
                exit_record=payload.exit_record or None,
                assets=payload.assets or None,
                handover=payload.handover or None,
                policy=payload.policy or None,
                organization_id=org,
                workflow_id=workflow_id,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateOffboardingTaskTool(BaseTool):
    spec = ToolSpec(
        name="create_offboarding_task",
        description="Create an exit checklist task (idempotent write).",
        category="offboarding",
        capability="offboarding.task.create",
        side_effect="write",
        allowed_agents=["offboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateOffboardingTaskInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateOffboardingTaskInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_offboarding_store().create_task(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                task_type=payload.task_type,
                details=payload.details,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ListOffboardingAssetsTool(BaseTool):
    spec = ToolSpec(
        name="list_offboarding_assets",
        description="List assets assigned to an employee for exit processing.",
        category="offboarding",
        capability="offboarding.asset.list",
        side_effect="read",
        allowed_agents=["exit_details_research", "checklist_analysis", "offboarding_analysis"],
        retryable=True,
        max_retries=2,
    )
    input_model = ListOffboardingAssetsInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ListOffboardingAssetsInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            assets = get_offboarding_store().list_assets(payload.employee_id, organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "employee_id": payload.employee_id.upper(),
            "assets": assets,
            "count": len(assets),
            "source": "simulated_offboarding_store",
        }


class RequestAssetReturnTool(BaseTool):
    spec = ToolSpec(
        name="request_asset_return",
        description="Create/record an asset-return request (controlled write).",
        category="offboarding",
        capability="offboarding.asset.return",
        side_effect="write",
        allowed_agents=["offboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = RequestAssetReturnInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = RequestAssetReturnInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_offboarding_store().request_asset_return(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                asset_id=payload.asset_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateOffboardingHandoverTool(BaseTool):
    spec = ToolSpec(
        name="create_offboarding_handover",
        description="Create a knowledge/document handover task (idempotent write).",
        category="offboarding",
        capability="offboarding.handover.create",
        side_effect="write",
        allowed_agents=["offboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateOffboardingHandoverInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateOffboardingHandoverInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_offboarding_store().create_handover(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                projects=payload.projects or None,
                documents=payload.documents or None,
                knowledge_areas=payload.knowledge_areas or None,
                manager=payload.manager,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ScheduleExitInterviewTool(BaseTool):
    spec = ToolSpec(
        name="schedule_exit_interview",
        description="Schedule a simulated exit interview (idempotent write).",
        category="offboarding",
        capability="offboarding.exit_interview.schedule",
        side_effect="write",
        allowed_agents=["offboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = ScheduleExitInterviewInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ScheduleExitInterviewInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_offboarding_store().schedule_exit_interview(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                scheduled_for=payload.scheduled_for,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateAccessRevokeRequestTool(BaseTool):
    spec = ToolSpec(
        name="create_access_revoke_request",
        description="Create a system-access revocation request (not automatic revocation).",
        category="offboarding",
        capability="offboarding.access.revoke_request",
        side_effect="write",
        allowed_agents=["offboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateAccessRevokeRequestInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateAccessRevokeRequestInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_offboarding_store().create_access_revoke_request(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                systems=payload.systems,
                privileged=payload.privileged,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class UpdateOffboardingStatusTool(BaseTool):
    spec = ToolSpec(
        name="update_offboarding_status",
        description="Update offboarding workflow status (idempotent write).",
        category="offboarding",
        capability="offboarding.status.update",
        side_effect="write",
        allowed_agents=["offboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = UpdateOffboardingStatusInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = UpdateOffboardingStatusInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_offboarding_store().update_status(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                status=payload.status,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
