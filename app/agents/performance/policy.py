"""Performance Policy Agent: authoritative policy lookup/validation via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def performance_policy_agent(state: WorkflowState) -> dict[str, Any]:
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    summary = dict(analysis.get("summary") or {})
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="performance_policy",
        query="performance improvement process approval requirements manager review",
        workflow_type="performance",
    )
    patches.append(knowledge_patch)

    policy_result, policy_patch = invoke_tool(
        state,
        agent="performance_policy",
        name="get_performance_policy",
        payload={},
    )
    patches.append(policy_patch)
    policy = dict(policy_result.data or {}) if policy_result.success else {}
    if not policy_result.success:
        errors.append(policy_result.error_message or "get_performance_policy failed.")

    validation: dict[str, Any] = {}
    if analysis.get("scan_mode"):
        validation = {
            "policy_id": policy.get("policy_id"),
            "severity": "normal",
            "outcome_hint": "recommend",
            "eligible_for_action": False,
            "requires_human_approval": False,
            "violations": [],
            "warnings": [],
            "exceptions": ["Scan mode uses aggregated findings; no single-employee action."],
            "plan_type": None,
        }
    elif employee and summary:
        validate_result, validate_patch = invoke_tool(
            state,
            agent="performance_policy",
            name="validate_performance_policy",
            payload={
                "employee": employee,
                "performance_summary": summary,
            },
        )
        patches.append(validate_patch)
        if validate_result.success and validate_result.data:
            validation = dict(validate_result.data)
        else:
            errors.append(validate_result.error_message or "validate_performance_policy failed.")
    else:
        validation = {
            "policy_id": policy.get("policy_id"),
            "severity": "blocked",
            "outcome_hint": "blocked",
            "eligible_for_action": False,
            "requires_human_approval": False,
            "violations": ["Employee or performance summary missing for policy validation."],
            "warnings": [],
            "exceptions": [],
            "plan_type": None,
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
        "plan_type": validation.get("plan_type"),
        "consider_attendance_signals": bool(validation.get("consider_attendance_signals")),
        "validation": validation,
    }

    _, memory_patch = append_short_term(
        state,
        agent="performance_policy",
        content=(
            f"Policy {policy_results.get('policy_id')}: severity={policy_results['severity']}; "
            f"violations={len(policy_results['violations'])}; "
            f"warnings={len(policy_results['warnings'])}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "performance_policy",
        (
            f"Applied performance policy; severity={policy_results['severity']}; "
            f"approval_required={policy_results['requires_human_approval']}."
        ),
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
