"""Offboarding Analysis: combine employee, exit, checklist, assets, and policy."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState


def offboarding_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    employee = state.get("employee_data") or {}
    policy = state.get("policy_results") or {}
    request = (state.get("metadata") or {}).get("offboarding_request") or {}
    patches: list[dict[str, Any]] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="offboarding_analysis",
        query="resignation process knowledge transfer manager responsibilities",
        workflow_type="offboarding",
    )
    patches.append(knowledge_patch)

    employee_id = str(
        employee.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    exit_record = dict(retrieved.get("exit_record") or {})
    checklist = dict(retrieved.get("checklist") or {})
    assets = list(retrieved.get("assets") or [])
    handover = dict(retrieved.get("handover") or {})
    outstanding_assets = [
        item
        for item in assets
        if str(item.get("return_status") or "").lower() in {"", "outstanding", "assigned"}
    ]

    blockers = list(policy.get("violations") or [])
    for item in checklist.get("blockers") or []:
        if item not in blockers:
            blockers.append(item)
    warnings = list(policy.get("warnings") or [])
    pending_tasks = list(checklist.get("pending_tasks") or [])

    if employee_id and not exit_record:
        blockers.append("Exit record was not retrieved.")
    if not employee_id:
        blockers.append("Employee ID is missing.")

    approval_requirements: list[str] = []
    if policy.get("requires_human_approval") or policy.get("privileged_access"):
        approval_requirements.append("privileged_access_revocation")
    if policy.get("exceptions"):
        for item in policy.get("exceptions") or []:
            if "employment-status" in str(item).lower() or "termination" in str(item).lower():
                approval_requirements.append("employment_status_change")
                break

    severity = str(policy.get("severity") or "")
    if severity == "blocked" or blockers:
        recommendation = "blocked"
    elif policy.get("requires_human_approval") or severity == "pending_approval":
        recommendation = "pending_approval"
    elif severity == "ready" and employee_id and exit_record:
        recommendation = "ready"
    elif employee_id and exit_record:
        recommendation = "recommend"
    else:
        recommendation = "blocked"

    analysis = {
        "employee_id": employee_id or None,
        "department": employee.get("department"),
        "manager": employee.get("manager"),
        "operation": request.get("operation"),
        "exit_type": exit_record.get("exit_type") or request.get("exit_type"),
        "resignation_date": exit_record.get("resignation_date"),
        "last_working_day": retrieved.get("last_working_day"),
        "notice_period_days": retrieved.get("notice_period_days"),
        "exit_record": exit_record,
        "checklist": checklist,
        "pending_tasks": pending_tasks,
        "completed_tasks": list(checklist.get("completed_tasks") or []),
        "assets": assets,
        "outstanding_assets": outstanding_assets,
        "handover": handover,
        "access_systems": list(retrieved.get("access_systems") or []),
        "privileged_access": bool(retrieved.get("privileged_access") or policy.get("privileged_access")),
        "privileged_systems": list(retrieved.get("privileged_systems") or []),
        "blockers": blockers,
        "warnings": warnings,
        "approval_requirements": sorted(set(approval_requirements)),
        "recommendation": recommendation,
        "policy_severity": severity,
        "approval_level": policy.get("approval_level"),
        "mandatory_tasks": ["manager_review", "hr_review"],
    }

    _, memory_patch = append_short_term(
        state,
        agent="offboarding_analysis",
        content=(
            f"Offboarding analysis employee={employee_id or 'unknown'}; "
            f"recommendation={recommendation}; pending={len(pending_tasks)}; "
            f"assets={len(outstanding_assets)}; privileged={analysis['privileged_access']}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "offboarding_analysis",
        (
            f"Analyzed offboarding for {employee_id or 'unknown'}; "
            f"recommendation={recommendation}; blockers={len(blockers)}."
        ),
        analysis_results=analysis,
        **combine_patches(*patches),
    )
