"""Policy Agent: load leave policy and evaluate deterministic rules."""

from __future__ import annotations

from typing import Any

from app.agents.common import leave_request_from_state, node_update
from app.orchestration.state import WorkflowState
from app.services.hr_data import load_leave_policy


def policy_agent(state: WorkflowState) -> dict[str, Any]:
    policy = load_leave_policy()
    rules = dict(policy.get("rules", {}))
    leave_request = leave_request_from_state(state)
    employee = state.get("employee_data") or {}
    days = leave_request.get("days")
    leave_type = leave_request.get("leave_type", "annual")

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

    if not employee and leave_request.get("employee_id"):
        violations.append("Policy cannot be fully evaluated without an employee record.")

    policy_results = {
        "policy_id": policy.get("policy_id"),
        "title": policy.get("title"),
        "leave_type": leave_type,
        "rules": rules,
        "violations": violations,
        "warnings": warnings,
        "requires_human_approval": requires_human_approval,
        "eligible": len(violations) == 0,
    }

    summary = (
        f"Applied {policy.get('policy_id')}: "
        f"{len(violations)} violation(s), {len(warnings)} warning(s)."
    )
    return node_update("policy", summary, policy_results=policy_results)
