"""Attendance Policy Agent: authoritative policy lookup/validation via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def attendance_policy_agent(state: WorkflowState) -> dict[str, Any]:
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    summary = dict(analysis.get("summary") or {})
    patches: list[dict[str, Any]] = []
    errors: list[str] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="attendance_policy",
        query="attendance policy late arrival escalation manager review",
        workflow_type="attendance",
    )
    patches.append(knowledge_patch)

    policy_result, policy_patch = invoke_tool(
        state,
        agent="attendance_policy",
        name="get_attendance_policy",
        payload={},
    )
    patches.append(policy_patch)
    policy = dict(policy_result.data or {}) if policy_result.success else {}
    if not policy_result.success:
        errors.append(policy_result.error_message or "get_attendance_policy failed.")

    validation: dict[str, Any] = {}
    if analysis.get("scan_mode"):
        # Department/org scans report findings; no single-employee policy gate.
        validation = {
            "policy_id": policy.get("policy_id"),
            "severity": "normal",
            "outcome_hint": "recommend",
            "eligible_for_action": False,
            "requires_human_approval": False,
            "violations": [],
            "warnings": [],
            "exceptions": ["Scan mode uses aggregated findings; no single-employee action."],
        }
    elif employee and summary:
        validate_result, validate_patch = invoke_tool(
            state,
            agent="attendance_policy",
            name="validate_attendance_policy",
            payload={
                "employee": employee,
                "attendance_summary": summary,
            },
        )
        patches.append(validate_patch)
        if validate_result.success and validate_result.data:
            validation = dict(validate_result.data)
        else:
            errors.append(validate_result.error_message or "validate_attendance_policy failed.")
    else:
        validation = {
            "policy_id": policy.get("policy_id"),
            "severity": "blocked",
            "outcome_hint": "blocked",
            "eligible_for_action": False,
            "requires_human_approval": False,
            "violations": ["Employee or attendance summary missing for policy validation."],
            "warnings": [],
            "exceptions": [],
        }

    policy_results = {
        "policy_id": validation.get("policy_id") or policy.get("policy_id"),
        "policy": policy,
        "severity": validation.get("severity"),
        "outcome_hint": validation.get("outcome_hint"),
        "eligible": validation.get("severity") != "blocked",
        "eligible_for_action": bool(validation.get("eligible_for_action")),
        "violations": list(validation.get("violations") or []),
        "warnings": list(validation.get("warnings") or []),
        "exceptions": list(validation.get("exceptions") or []),
        "requires_human_approval": bool(validation.get("requires_human_approval")),
        "validation": validation,
    }

    _, memory_patch = append_short_term(
        state,
        agent="attendance_policy",
        content=(
            f"Policy {policy_results.get('policy_id')}: severity={policy_results['severity']}; "
            f"violations={len(policy_results['violations'])}; "
            f"warnings={len(policy_results['warnings'])}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "attendance_policy",
        (
            f"Applied attendance policy; severity={policy_results['severity']}; "
            f"approval_required={policy_results['requires_human_approval']}."
        ),
        policy_results=policy_results,
        errors=errors,
        **combine_patches(*patches),
    )
