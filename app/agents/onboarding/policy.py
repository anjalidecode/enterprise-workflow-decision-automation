"""Onboarding Policy Agent: authoritative policy lookup/validation via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def onboarding_policy_agent(state: WorkflowState) -> dict[str, Any]:
    employee = state.get("employee_data") or (state.get("retrieved_data") or {}).get("employee") or {}
    verification = (state.get("retrieved_data") or {}).get("document_verification") or {}
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="onboarding_policy",
        query="onboarding approval procedures system access equipment",
        workflow_type="onboarding",
    )
    patches.append(knowledge_patch)

    policy_result, policy_patch = invoke_tool(
        state,
        agent="onboarding_policy",
        name="get_onboarding_policy",
        payload={},
    )
    patches.append(policy_patch)
    policy = dict(policy_result.data or {}) if policy_result.success else {}
    if not policy_result.success:
        errors.append(policy_result.error_message or "get_onboarding_policy failed.")

    validation: dict[str, Any] = {}
    if employee:
        validate_result, validate_patch = invoke_tool(
            state,
            agent="onboarding_policy",
            name="validate_onboarding_policy",
            payload={
                "employee": employee,
                "document_verification": verification,
            },
        )
        patches.append(validate_patch)
        if validate_result.success and validate_result.data:
            validation = dict(validate_result.data)
        else:
            errors.append(validate_result.error_message or "validate_onboarding_policy failed.")
    else:
        errors.append("Policy validation skipped because employee data is missing.")

    policy_results = {
        "policy_id": validation.get("policy_id") or policy.get("policy_id"),
        "policy": policy,
        "eligible": bool(validation.get("eligible")),
        "violations": list(validation.get("violations") or []),
        "warnings": list(validation.get("warnings") or []),
        "requires_human_approval": bool(validation.get("requires_human_approval")),
        "mandatory_tasks": list(validation.get("mandatory_tasks") or policy.get("mandatory_tasks") or []),
        "equipment_required": list(validation.get("equipment_required") or []),
        "access_required": list(validation.get("access_required") or []),
        "privileged_access_required": list(validation.get("privileged_access_required") or []),
        "onboarding_track": validation.get("onboarding_track"),
        "validation": validation,
    }

    _, memory_patch = append_short_term(
        state,
        agent="onboarding_policy",
        content=(
            f"Policy {policy_results.get('policy_id')}: eligible={policy_results['eligible']}; "
            f"violations={len(policy_results['violations'])}; "
            f"privileged_approval={policy_results['requires_human_approval']}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "onboarding_policy",
        (
            f"Applied onboarding policy; eligible={policy_results['eligible']}; "
            f"approval_required={policy_results['requires_human_approval']}."
        ),
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
