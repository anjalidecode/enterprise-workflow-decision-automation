"""Offboarding Policy Agent: authoritative policy lookup/validation via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def offboarding_policy_agent(state: WorkflowState) -> dict[str, Any]:
    employee = state.get("employee_data") or {}
    retrieved = state.get("retrieved_data") or {}
    exit_record = dict(retrieved.get("exit_record") or {})
    checklist = dict(retrieved.get("checklist") or {})
    assets = list(retrieved.get("assets") or [])
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="offboarding_policy",
        query="notice period exit checklist asset return access revocation",
        workflow_type="offboarding",
    )
    patches.append(knowledge_patch)

    policy_result, policy_patch = invoke_tool(
        state,
        agent="offboarding_policy",
        name="get_offboarding_policy",
        payload={},
    )
    patches.append(policy_patch)
    policy = dict(policy_result.data or {}) if policy_result.success else {}
    if not policy_result.success:
        errors.append(policy_result.error_message or "get_offboarding_policy failed.")

    validation: dict[str, Any] = {}
    if employee and exit_record:
        validate_result, validate_patch = invoke_tool(
            state,
            agent="offboarding_policy",
            name="validate_offboarding_policy",
            payload={
                "employee": employee,
                "exit_record": exit_record,
                "checklist": checklist,
                "assets": assets,
                "policy": policy,
            },
        )
        patches.append(validate_patch)
        if validate_result.success and validate_result.data:
            validation = dict(validate_result.data)
        else:
            errors.append(validate_result.error_message or "validate_offboarding_policy failed.")
    else:
        validation = {
            "policy_id": policy.get("policy_id"),
            "severity": "blocked",
            "outcome_hint": "blocked",
            "eligible_for_action": False,
            "requires_human_approval": False,
            "violations": ["Employee or exit record missing for policy validation."],
            "warnings": [],
            "exceptions": [],
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
        "privileged_access": bool(validation.get("privileged_access")),
        "validation": validation,
    }

    _, memory_patch = append_short_term(
        state,
        agent="offboarding_policy",
        content=(
            f"Policy {policy_results.get('policy_id')}: severity={policy_results['severity']}; "
            f"violations={len(policy_results['violations'])}; "
            f"approval={policy_results['requires_human_approval']}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "offboarding_policy",
        (
            f"Applied offboarding policy; severity={policy_results['severity']}; "
            f"approval_required={policy_results['requires_human_approval']}."
        ),
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
