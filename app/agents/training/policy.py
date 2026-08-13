"""Training Policy Agent: authoritative policy lookup/validation via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def training_policy_agent(state: WorkflowState) -> dict[str, Any]:
    employee = state.get("employee_data") or {}
    retrieved = state.get("retrieved_data") or {}
    primary = dict(retrieved.get("recommended_course") or {})
    alternatives = list(retrieved.get("alternative_courses") or [])
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="training_policy",
        query="training prerequisites manager approval course enrollment",
        workflow_type="training",
    )
    patches.append(knowledge_patch)

    policy_result, policy_patch = invoke_tool(
        state,
        agent="training_policy",
        name="get_training_policy",
        payload={},
    )
    patches.append(policy_patch)
    policy = dict(policy_result.data or {}) if policy_result.success else {}
    if not policy_result.success:
        errors.append(policy_result.error_message or "get_training_policy failed.")

    validation: dict[str, Any] = {}
    if employee and primary:
        validate_result, validate_patch = invoke_tool(
            state,
            agent="training_policy",
            name="validate_training_policy",
            payload={
                "employee": employee,
                "course": primary,
                "courses": [primary, *alternatives],
                "prerequisites": list(primary.get("prerequisites") or []),
                "employee_skills": list(retrieved.get("employee_skills") or []),
                "policy": policy,
            },
        )
        patches.append(validate_patch)
        if validate_result.success and validate_result.data:
            validation = dict(validate_result.data)
        else:
            errors.append(validate_result.error_message or "validate_training_policy failed.")
    else:
        validation = {
            "policy_id": policy.get("policy_id"),
            "severity": "blocked",
            "outcome_hint": "blocked",
            "eligible_for_action": False,
            "requires_human_approval": False,
            "violations": ["Employee or recommended course missing for policy validation."],
            "warnings": [],
            "exceptions": [],
            "primary_course_id": primary.get("course_id") if primary else None,
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
        "primary_course_id": validation.get("primary_course_id"),
        "validation": validation,
    }

    _, memory_patch = append_short_term(
        state,
        agent="training_policy",
        content=(
            f"Policy {policy_results.get('policy_id')}: severity={policy_results['severity']}; "
            f"violations={len(policy_results['violations'])}; "
            f"approval={policy_results['requires_human_approval']}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "training_policy",
        (
            f"Applied training policy; severity={policy_results['severity']}; "
            f"approval_required={policy_results['requires_human_approval']}."
        ),
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
