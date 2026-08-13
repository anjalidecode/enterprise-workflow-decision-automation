"""Onboarding domain tools. Agents never access onboarding JSON directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.onboarding_store import get_onboarding_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import from_service_error


class EmployeeDocumentsInput(BaseModel):
    employee_id: str = Field(min_length=1)
    organization_id: str = ""


class VerifyDocumentsInput(BaseModel):
    employee_id: str = Field(min_length=1)
    organization_id: str = ""


class OnboardingPolicyLookupInput(BaseModel):
    organization_id: str = ""


class ValidateOnboardingPolicyInput(BaseModel):
    employee: dict[str, Any]
    document_verification: dict[str, Any]
    organization_id: str = ""


class CreateOnboardingTaskInput(BaseModel):
    employee_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    workflow_id: str = ""
    assignee: str = ""
    organization_id: str = ""


class ListOnboardingTasksInput(BaseModel):
    employee_id: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class RequestEquipmentInput(BaseModel):
    employee_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class RequestAccessInput(BaseModel):
    employee_id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    workflow_id: str = ""
    privileged: bool = False
    organization_id: str = ""


class UpdateOnboardingStatusInput(BaseModel):
    employee_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class GetEmployeeDocumentsTool(BaseTool):
    spec = ToolSpec(
        name="get_employee_documents",
        description="Retrieve document metadata for an employee.",
        category="onboarding",
        capability="employee.documents",
        side_effect="read",
        allowed_agents=["document_verification", "onboarding_analysis"],
    )
    input_model = EmployeeDocumentsInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = EmployeeDocumentsInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            documents = get_onboarding_store().list_documents(
                payload.employee_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "employee_id": payload.employee_id.upper(),
            "documents": documents,
            "count": len(documents),
            "source": "simulated_onboarding_store",
        }


class VerifyEmployeeDocumentsTool(BaseTool):
    spec = ToolSpec(
        name="verify_employee_documents",
        description="Verify mandatory onboarding documents for an employee.",
        category="onboarding",
        capability="employee.document.verify",
        side_effect="read",
        allowed_agents=["document_verification", "onboarding_policy", "onboarding_analysis"],
    )
    input_model = VerifyDocumentsInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = VerifyDocumentsInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_onboarding_store().verify_documents(
                payload.employee_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class GetOnboardingPolicyTool(BaseTool):
    spec = ToolSpec(
        name="get_onboarding_policy",
        description="Retrieve the structured onboarding policy.",
        category="onboarding",
        capability="onboarding.policy.lookup",
        side_effect="read",
        allowed_agents=["onboarding_policy"],
    )
    input_model = OnboardingPolicyLookupInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = OnboardingPolicyLookupInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_onboarding_store().get_policy(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ValidateOnboardingPolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_onboarding_policy",
        description="Validate onboarding eligibility against structured policy.",
        category="onboarding",
        capability="onboarding.policy.validate",
        side_effect="read",
        allowed_agents=["onboarding_policy"],
    )
    input_model = ValidateOnboardingPolicyInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidateOnboardingPolicyInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_onboarding_store().validate_onboarding_policy(
                employee=payload.employee,
                document_verification=payload.document_verification,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateOnboardingTaskTool(BaseTool):
    spec = ToolSpec(
        name="create_onboarding_task",
        description="Create an onboarding task (idempotent write).",
        category="onboarding",
        capability="onboarding.task.create",
        side_effect="write",
        allowed_agents=["onboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = CreateOnboardingTaskInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CreateOnboardingTaskInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_onboarding_store().create_task(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                task_type=payload.task_type,
                organization_id=org,
                assignee=payload.assignee,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ListOnboardingTasksTool(BaseTool):
    spec = ToolSpec(
        name="list_onboarding_tasks",
        description="List onboarding tasks for an employee.",
        category="onboarding",
        capability="onboarding.task.list",
        side_effect="read",
        allowed_agents=["onboarding_action", "onboarding_response", "onboarding_analysis"],
    )
    input_model = ListOnboardingTasksInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ListOnboardingTasksInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            tasks = get_onboarding_store().list_tasks(
                payload.employee_id,
                organization_id=org,
                workflow_id=workflow_id,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return {
            "employee_id": payload.employee_id.upper(),
            "tasks": tasks,
            "count": len(tasks),
            "source": "simulated_onboarding_store",
        }


class RequestEquipmentTool(BaseTool):
    spec = ToolSpec(
        name="request_equipment",
        description="Request onboarding equipment (idempotent write).",
        category="onboarding",
        capability="onboarding.equipment.request",
        side_effect="write",
        allowed_agents=["onboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = RequestEquipmentInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = RequestEquipmentInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_onboarding_store().request_equipment(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                item=payload.item,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class RequestSystemAccessTool(BaseTool):
    spec = ToolSpec(
        name="request_system_access",
        description="Request system access for onboarding (idempotent write).",
        category="onboarding",
        capability="onboarding.access.request",
        side_effect="write",
        allowed_agents=["onboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = RequestAccessInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = RequestAccessInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_onboarding_store().request_access(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                system=payload.system,
                organization_id=org,
                privileged=payload.privileged,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class UpdateOnboardingStatusTool(BaseTool):
    spec = ToolSpec(
        name="update_onboarding_status",
        description="Update onboarding status (idempotent write).",
        category="onboarding",
        capability="onboarding.status.update",
        side_effect="write",
        allowed_agents=["onboarding_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = UpdateOnboardingStatusInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = UpdateOnboardingStatusInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_onboarding_store().update_status(
                workflow_id=workflow_id,
                employee_id=payload.employee_id,
                status=payload.status,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
