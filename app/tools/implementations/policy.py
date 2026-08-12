"""Leave policy lookup and validation tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.errors import SimulatedServiceError
from app.services.hr_store import get_hr_store
from app.tools.contracts import BaseTool, ToolContext, ToolSpec
from app.tools.errors import from_service_error


class GetLeavePolicyInput(BaseModel):
    policy_id: str | None = None


class GetLeavePolicyOutput(BaseModel):
    policy_id: str
    title: str
    version: str | None = None
    leave_type: str
    rules: dict[str, Any]
    rule_notes: dict[str, Any] = Field(default_factory=dict)
    source: str = "simulated_hr_store"


class ValidateLeavePolicyInput(BaseModel):
    employee_id: str | None = None
    days: int | None = None
    leave_type: str = "annual"
    start_date: str | None = None


class ValidateLeavePolicyOutput(BaseModel):
    policy_id: str | None = None
    title: str | None = None
    leave_type: str
    rules: dict[str, Any] = Field(default_factory=dict)
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    eligible: bool = False
    source: str = "simulated_hr_store"


def evaluate_leave_policy(
    *,
    policy: dict[str, Any],
    employee: dict[str, Any] | None,
    days: int | None,
    leave_type: str,
    employee_id: str | None,
) -> dict[str, Any]:
    rules = dict(policy.get("rules", {}))
    violations: list[str] = []
    warnings: list[str] = []
    requires_human_approval = False

    min_days = int(rules.get("minimum_days_per_request", 1))
    max_days = int(rules.get("maximum_days_per_request", 15))
    approval_threshold = int(rules.get("human_approval_required_if_days_gte", 5))

    if days is None:
        violations.append("Requested leave duration is missing.")
    else:
        if days < min_days:
            violations.append(f"Requested {days} day(s) is below the minimum of {min_days}.")
        if days > max_days:
            violations.append(f"Requested {days} day(s) exceeds the maximum of {max_days}.")
        if days >= approval_threshold:
            requires_human_approval = True
            warnings.append(
                f"Requests of {approval_threshold} or more days require human approval."
            )

    if rules.get("require_active_employment") and employee:
        if employee.get("employment_status") != "active":
            violations.append("Employee is not in active employment status.")

    if rules.get("require_available_balance") and employee and days is not None:
        available = int(employee.get("leave_balances", {}).get(leave_type, 0))
        if days > available:
            violations.append(
                f"Requested {days} day(s) exceeds available {leave_type} balance of {available}."
            )

    if not employee and employee_id:
        violations.append("Policy cannot be fully evaluated without an employee record.")

    return {
        "policy_id": policy.get("policy_id"),
        "title": policy.get("title"),
        "leave_type": leave_type,
        "rules": rules,
        "violations": violations,
        "warnings": warnings,
        "requires_human_approval": requires_human_approval,
        "eligible": len(violations) == 0,
        "source": "simulated_hr_store",
    }


class GetLeavePolicyTool(BaseTool):
    spec = ToolSpec(
        name="get_leave_policy",
        description="Load the current annual leave policy.",
        category="policy",
        capability="policy.lookup",
        side_effect="read",
        allowed_agents=["policy"],
        retryable=True,
        max_retries=2,
    )
    input_model = GetLeavePolicyInput
    output_model = GetLeavePolicyOutput

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        try:
            policy = get_hr_store().get_leave_policy(organization_id=context.organization_id)
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        output = GetLeavePolicyOutput(
            policy_id=str(policy.get("policy_id", "")),
            title=str(policy.get("title", "")),
            version=policy.get("version"),
            leave_type=str(policy.get("leave_type", "annual")),
            rules=dict(policy.get("rules") or {}),
            rule_notes=dict(policy.get("rule_notes") or {}),
        )
        return output.model_dump()


class ValidateLeavePolicyTool(BaseTool):
    spec = ToolSpec(
        name="validate_leave_policy",
        description="Evaluate a leave request against HR leave policy rules.",
        category="policy",
        capability="policy.validate_leave",
        side_effect="read",
        allowed_agents=["policy"],
        retryable=False,
    )
    input_model = ValidateLeavePolicyInput
    output_model = ValidateLeavePolicyOutput

    def execute(self, inputs: BaseModel, context: ToolContext) -> dict[str, Any]:
        payload = ValidateLeavePolicyInput.model_validate(inputs.model_dump())
        store = get_hr_store()
        try:
            policy = store.get_leave_policy(organization_id=context.organization_id)
            employee = (
                store.get_employee(
                    payload.employee_id,
                    organization_id=context.organization_id,
                )
                if payload.employee_id
                else None
            )
        except SimulatedServiceError as error:
            raise from_service_error(error) from error
        result = evaluate_leave_policy(
            policy=policy,
            employee=employee,
            days=payload.days,
            leave_type=payload.leave_type,
            employee_id=payload.employee_id,
        )
        return ValidateLeavePolicyOutput.model_validate(result).model_dump()
