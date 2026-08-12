"""Leave impact calculation and balance update tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.hr_store import get_hr_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import ToolInvalidInputError, ToolNotFoundError, from_service_error


class CalculateLeaveImpactInput(BaseModel):
    employee_id: str | None = None
    days: int | None = None
    leave_type: str = "annual"


class CalculateLeaveImpactOutput(BaseModel):
    employee_id: str | None = None
    requested_days: int | None = None
    available_days: int | None = None
    remaining_after: int | None = None
    sufficient_balance: bool = False
    employment_active: bool = False
    employee_found: bool = False
    source: str = "simulated_hr_store"


class UpdateLeaveBalanceInput(BaseModel):
    employee_id: str = Field(min_length=1)
    days: int = Field(gt=0)
    leave_type: str = "annual"
    workflow_id: str = Field(min_length=1)
    start_date: str | None = None


class UpdateLeaveBalanceOutput(BaseModel):
    employee_id: str
    leave_type: str
    days: int
    previous_balance: int
    new_balance: int
    idempotent_replay: bool = False
    source: str = "simulated_hr_store"


class CalculateLeaveImpactTool(BaseTool):
    spec = ToolSpec(
        name="calculate_leave_impact",
        description="Calculate remaining leave balance and employment eligibility.",
        category="leave",
        capability="leave.impact",
        side_effect="read",
        allowed_agents=["analysis"],
        retryable=False,
    )
    input_model = CalculateLeaveImpactInput
    output_model = CalculateLeaveImpactOutput

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = CalculateLeaveImpactInput.model_validate(inputs.model_dump())
        try:
            employee = (
                get_hr_store().get_employee(payload.employee_id) if payload.employee_id else None
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        available = None
        remaining_after = None
        sufficient_balance = False
        employment_active = False
        if employee:
            employment_active = employee.get("employment_status") == "active"
            available = employee.get("leave_balances", {}).get(payload.leave_type)
            if isinstance(payload.days, int) and isinstance(available, int):
                remaining_after = available - payload.days
                sufficient_balance = payload.days <= available
        output = CalculateLeaveImpactOutput(
            employee_id=payload.employee_id,
            requested_days=payload.days,
            available_days=available,
            remaining_after=remaining_after,
            sufficient_balance=sufficient_balance,
            employment_active=employment_active,
            employee_found=employee is not None,
        )
        return output.model_dump()


class UpdateLeaveBalanceTool(BaseTool):
    spec = ToolSpec(
        name="update_leave_balance",
        description="Deduct approved leave from the simulated HR store. Idempotent per workflow request.",
        category="leave",
        capability="leave.balance.update",
        side_effect="write",
        allowed_agents=["action"],
        retryable=True,
        max_retries=2,
    )
    input_model = UpdateLeaveBalanceInput
    output_model = UpdateLeaveBalanceOutput

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = UpdateLeaveBalanceInput.model_validate(inputs.model_dump())
        store = get_hr_store()
        try:
            if store.get_employee(payload.employee_id) is None:
                raise ToolNotFoundError(f"Employee {payload.employee_id} was not found in the HR store.")
            if payload.days <= 0:
                raise ToolInvalidInputError("Leave days must be greater than zero.")
            result = store.update_leave_balance(
                workflow_id=payload.workflow_id,
                employee_id=payload.employee_id,
                days=payload.days,
                leave_type=payload.leave_type,
                start_date=payload.start_date,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        return UpdateLeaveBalanceOutput.model_validate(result).model_dump()
