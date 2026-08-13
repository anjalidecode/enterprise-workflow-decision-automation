"""Employee lookup tools backed by the simulated HR store."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.hr_store import get_hr_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import ToolNotFoundError, from_service_error


class GetEmployeeInput(BaseModel):
    employee_id: str = Field(min_length=1)


class GetEmployeeOutput(BaseModel):
    employee_id: str
    name: str
    department: str | None = None
    manager: str | None = None
    employment_status: str
    role: str | None = None
    joining_date: str | None = None
    leave_balances: dict[str, int]
    source: str = "simulated_hr_store"


class GetLeaveBalanceInput(BaseModel):
    employee_id: str = Field(min_length=1)
    leave_type: str = "annual"


class GetLeaveBalanceOutput(BaseModel):
    employee_id: str
    leave_type: str
    balance: int
    source: str = "simulated_hr_store"


class GetEmployeeTool(BaseTool):
    spec = ToolSpec(
        name="get_employee",
        description="Retrieve an employee record from the HR store.",
        category="employee",
        capability="employee.lookup",
        side_effect="read",
        allowed_agents=["research", "employee_research", "attendance_research", "performance_research", "training_research", "offboarding_employee_research", "employee_context"],
        retryable=True,
        max_retries=2,
    )
    input_model = GetEmployeeInput
    output_model = GetEmployeeOutput

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = GetEmployeeInput.model_validate(inputs.model_dump())
        try:
            employee = get_hr_store().get_employee(
                payload.employee_id,
                organization_id=context.organization_id,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        if employee is None:
            raise ToolNotFoundError(f"Employee {payload.employee_id} was not found in the HR store.")
        output = GetEmployeeOutput(
            employee_id=str(employee["employee_id"]),
            name=str(employee.get("name", "")),
            department=employee.get("department"),
            manager=employee.get("manager"),
            employment_status=str(employee.get("employment_status", "")),
            role=employee.get("role"),
            joining_date=employee.get("joining_date"),
            leave_balances=dict(employee.get("leave_balances") or {}),
        )
        return output.model_dump()


class GetLeaveBalanceTool(BaseTool):
    spec = ToolSpec(
        name="get_leave_balance",
        description="Retrieve a leave balance for an employee.",
        category="employee",
        capability="employee.leave_balance",
        side_effect="read",
        allowed_agents=["research", "analysis", "service_research"],
        retryable=True,
        max_retries=2,
    )
    input_model = GetLeaveBalanceInput
    output_model = GetLeaveBalanceOutput

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = GetLeaveBalanceInput.model_validate(inputs.model_dump())
        store = get_hr_store()
        try:
            employee = store.get_employee(
                payload.employee_id,
                organization_id=context.organization_id,
            )
            if employee is None:
                raise ToolNotFoundError(f"Employee {payload.employee_id} was not found in the HR store.")
            balance = store.get_leave_balance(
                payload.employee_id,
                payload.leave_type,
                organization_id=context.organization_id,
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        if balance is None:
            raise ToolNotFoundError(
                f"No {payload.leave_type} leave balance found for {payload.employee_id}."
            )
        output = GetLeaveBalanceOutput(
            employee_id=payload.employee_id,
            leave_type=payload.leave_type,
            balance=balance,
        )
        return output.model_dump()
