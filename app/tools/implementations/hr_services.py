"""HR Services domain tools. Agents never access HR services JSON directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.hr_services_store import get_hr_services_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import ToolNotFoundError, from_service_error


class HRServiceRequestCreateInput(BaseModel):
    employee_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    priority: str = "normal"
    status: str = "open"
    document_type: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class HRServiceRequestGetInput(BaseModel):
    request_id: str = Field(min_length=1)
    organization_id: str = ""


class HRServiceRequestUpdateInput(BaseModel):
    request_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    workflow_id: str = ""
    organization_id: str = ""


class HRServiceDocumentRequestInput(BaseModel):
    employee_id: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    summary: str = ""
    workflow_id: str = ""
    organization_id: str = ""


class HRServiceRouteToHRInput(BaseModel):
    request_id: str = Field(min_length=1)
    reason: str = ""
    priority: str = "normal"
    workflow_id: str = ""
    organization_id: str = ""


class HRServicePolicyLookupInput(BaseModel):
    organization_id: str = ""


class ValidateHRServicePolicyInput(BaseModel):
    category: str = Field(min_length=1)
    employee: dict[str, Any] = Field(default_factory=dict)
    authorization: dict[str, Any] = Field(default_factory=dict)
    service_data: dict[str, Any] = Field(default_factory=dict)
    organization_id: str = ""


class EvaluateHRServiceAuthInput(BaseModel):
    category: str = Field(min_length=1)
    target_employee_id: str = ""
    requester_user_id: str = ""
    requester_role: str = ""
    candidate_id: str = ""
    organization_id: str = ""


class CreateHRServiceRequestTool(BaseTool):
    spec = ToolSpec(
        name="create_hr_service_request",
        description="Create an HR service ticket/request with idempotency.",
        category="hr_services",
        capability="hr_service.request.create",
        side_effect="write",
        allowed_agents=["service_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = HRServiceRequestCreateInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = HRServiceRequestCreateInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_hr_services_store().create_request(
                employee_id=payload.employee_id,
                category=payload.category,
                summary=payload.summary,
                priority=payload.priority,
                status=payload.status,
                workflow_id=workflow_id,
                organization_id=org,
                document_type=payload.document_type or None,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class GetHRServiceRequestTool(BaseTool):
    spec = ToolSpec(
        name="get_hr_service_request",
        description="Retrieve an HR service request by id.",
        category="hr_services",
        capability="hr_service.request.get",
        side_effect="read",
        allowed_agents=["service_research", "service_analysis", "service_policy"],
        retryable=True,
        max_retries=2,
    )
    input_model = HRServiceRequestGetInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = HRServiceRequestGetInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            record = get_hr_services_store().get_request(
                payload.request_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        if record is None:
            raise ToolNotFoundError(f"HR service request {payload.request_id} not found.")
        return {**record, "source": "simulated_hr_services_store"}


class UpdateHRServiceRequestTool(BaseTool):
    spec = ToolSpec(
        name="update_hr_service_request",
        description="Update HR service request status.",
        category="hr_services",
        capability="hr_service.request.update",
        side_effect="write",
        allowed_agents=["service_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = HRServiceRequestUpdateInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = HRServiceRequestUpdateInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_hr_services_store().update_request(
                request_id=payload.request_id,
                status=payload.status,
                workflow_id=workflow_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class CreateHRDocumentRequestTool(BaseTool):
    spec = ToolSpec(
        name="create_hr_document_request",
        description="Create a simulated HR document request.",
        category="hr_services",
        capability="hr_service.document.request",
        side_effect="write",
        allowed_agents=["service_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = HRServiceDocumentRequestInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = HRServiceDocumentRequestInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_hr_services_store().create_document_request(
                employee_id=payload.employee_id,
                document_type=payload.document_type,
                workflow_id=workflow_id,
                organization_id=org,
                summary=payload.summary,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class RouteHRServiceToHRTool(BaseTool):
    spec = ToolSpec(
        name="route_hr_service_to_hr",
        description="Route an HR service request to the HR queue.",
        category="hr_services",
        capability="hr_service.route_to_hr",
        side_effect="write",
        allowed_agents=["service_action"],
        idempotent=True,
        retryable=True,
        max_retries=2,
    )
    input_model = HRServiceRouteToHRInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = HRServiceRouteToHRInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            return get_hr_services_store().route_to_hr(
                request_id=payload.request_id,
                reason=payload.reason,
                workflow_id=workflow_id,
                organization_id=org,
                priority=payload.priority,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class GetHRServicePolicyTool(BaseTool):
    spec = ToolSpec(
        name="get_hr_service_policy",
        description="Retrieve the structured HR services policy.",
        category="policy",
        capability="hr_service.policy.lookup",
        side_effect="read",
        allowed_agents=["service_policy"],
    )
    input_model = HRServicePolicyLookupInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = HRServicePolicyLookupInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_hr_services_store().get_policy(organization_id=org)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class ValidateHRServicePolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_hr_service_policy",
        description="Validate an HR service request against policy and authorization.",
        category="policy",
        capability="hr_service.policy.validate",
        side_effect="read",
        allowed_agents=["service_policy"],
    )
    input_model = ValidateHRServicePolicyInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidateHRServicePolicyInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_hr_services_store().validate_service_policy(
                category=payload.category,
                employee=payload.employee or None,
                authorization=payload.authorization or None,
                service_data=payload.service_data or None,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error


class EvaluateHRServiceAuthorizationTool(BaseTool):
    spec = ToolSpec(
        name="evaluate_hr_service_authorization",
        description="Evaluate whether the requester may access the target HR service data.",
        category="policy",
        capability="hr_service.authorization.evaluate",
        side_effect="read",
        allowed_agents=["service_policy", "service_analysis", "employee_context"],
    )
    input_model = EvaluateHRServiceAuthInput
    output_model = BaseModel

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = EvaluateHRServiceAuthInput.model_validate(inputs.model_dump())
        org = payload.organization_id or context.organization_id
        try:
            return get_hr_services_store().evaluate_authorization(
                category=payload.category,
                target_employee_id=payload.target_employee_id,
                requester_user_id=payload.requester_user_id or context.user_id,
                requester_role=payload.requester_role or context.user_role,
                candidate_id=payload.candidate_id,
                organization_id=org,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
