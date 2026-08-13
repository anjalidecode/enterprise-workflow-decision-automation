"""Service Policy: auto-complete eligibility, approval needs, disclosure limits."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def service_policy_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("hr_services_request") or {}
    employee = state.get("employee_data") or {}
    retrieved = state.get("retrieved_data") or {}
    authorization = (state.get("metadata") or {}).get("authorization") or retrieved.get(
        "authorization"
    ) or {}
    service_data = dict(retrieved.get("service_data") or {})
    category = str(request.get("category") or "general_hr")
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="service_policy",
        query="confidentiality escalation service ticket lifecycle profile change",
        workflow_type="hr_services",
    )
    patches.append(knowledge_patch)

    policy_result, policy_patch = invoke_tool(
        state,
        agent="service_policy",
        name="get_hr_service_policy",
        payload={},
    )
    patches.append(policy_patch)
    policy = dict(policy_result.data or {}) if policy_result.success else {}
    if not policy_result.success:
        errors.append(policy_result.error_message or "get_hr_service_policy failed.")

    validate_result, validate_patch = invoke_tool(
        state,
        agent="service_policy",
        name="validate_hr_service_policy",
        payload={
            "category": category,
            "employee": employee,
            "authorization": authorization,
            "service_data": service_data,
        },
    )
    patches.append(validate_patch)
    validation: dict[str, Any] = {}
    if validate_result.success and validate_result.data:
        validation = dict(validate_result.data)
    else:
        errors.append(validate_result.error_message or "validate_hr_service_policy failed.")
        validation = {
            "policy_id": policy.get("policy_id"),
            "severity": "blocked",
            "eligible_for_action": False,
            "requires_human_approval": False,
            "violations": ["Policy validation failed."],
            "warnings": [],
            "route_hint": "escalate",
        }

    policy_results = {
        "policy_id": validation.get("policy_id") or policy.get("policy_id"),
        "policy": policy,
        "severity": validation.get("severity"),
        "outcome_hint": validation.get("outcome_hint"),
        "eligible": validation.get("severity") not in {None, "blocked"},
        "eligible_for_action": bool(validation.get("eligible_for_action")),
        "violations": list(validation.get("violations") or []),
        "warnings": list(validation.get("warnings") or []),
        "exceptions": list(validation.get("exceptions") or []),
        "requires_human_approval": bool(validation.get("requires_human_approval")),
        "approval_level": validation.get("approval_level"),
        "route_hint": validation.get("route_hint") or "resolve",
        "category": category,
        "authorization": authorization,
        "validation": validation,
    }

    _, memory_patch = append_short_term(
        state,
        agent="service_policy",
        content=(
            f"Policy {policy_results.get('policy_id')}: severity={policy_results['severity']}; "
            f"route={policy_results['route_hint']}; "
            f"approval={policy_results['requires_human_approval']}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "service_policy",
        (
            f"Applied HR services policy; severity={policy_results['severity']}; "
            f"route_hint={policy_results['route_hint']}."
        ),
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
