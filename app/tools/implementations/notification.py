"""Employee notification tool backed by the simulated notification sink."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.notifications import get_notification_service
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import from_service_error


class NotifyEmployeeInput(BaseModel):
    employee_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    workflow_id: str = ""


class NotifyEmployeeOutput(BaseModel):
    employee_id: str
    message: str
    workflow_id: str
    channel: str
    status: str
    sent_at: str
    source: str


class NotifyEmployeeTool(BaseTool):
    spec = ToolSpec(
        name="notify_employee",
        description="Send a simulated notification to an employee.",
        category="notification",
        capability="notification.send",
        side_effect="write",
        allowed_agents=["action"],
        retryable=True,
        max_retries=2,
    )
    input_model = NotifyEmployeeInput
    output_model = NotifyEmployeeOutput

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = NotifyEmployeeInput.model_validate(inputs.model_dump())
        workflow_id = payload.workflow_id or context.workflow_id
        try:
            record = get_notification_service().send(
                employee_id=payload.employee_id,
                message=payload.message,
                workflow_id=workflow_id,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return NotifyEmployeeOutput.model_validate(record).model_dump()
