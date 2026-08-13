"""Service Analysis: combine request, context, service data, policy, knowledge."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState


def service_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("hr_services_request") or {}
    employee = state.get("employee_data") or {}
    policy = state.get("policy_results") or {}
    retrieved = state.get("retrieved_data") or {}
    service_data = dict(retrieved.get("service_data") or {})
    authorization = (state.get("metadata") or {}).get("authorization") or retrieved.get(
        "authorization"
    ) or {}
    category = str(request.get("category") or policy.get("category") or "general_hr")
    patches: list[dict[str, Any]] = []

    _, knowledge_patch = search_knowledge(
        state,
        agent="service_analysis",
        query="hr support document request payroll routing benefits",
        workflow_type="hr_services",
    )
    patches.append(knowledge_patch)

    employee_id = str(
        employee.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )

    blockers = list(policy.get("violations") or [])
    warnings = list(policy.get("warnings") or [])
    if authorization.get("disclosure_blocked"):
        if authorization.get("reason") not in blockers:
            blockers.append(str(authorization.get("reason")))

    requires_document = category == "employment_document"
    requires_ticket = category in {
        "employee_profile",
        "payroll_routing",
        "general_hr",
        "employment_document",
    }
    requires_approval = bool(policy.get("requires_human_approval")) or category == "employee_profile"
    requires_escalation = category == "payroll_routing" or str(policy.get("severity")) == "escalate"

    severity = str(policy.get("severity") or "")
    if severity == "blocked" or blockers:
        disposition = "blocked"
    elif requires_approval and category == "employee_profile":
        disposition = "requires_approval"
    elif requires_escalation:
        disposition = "requires_escalation"
    elif requires_document:
        disposition = "requires_document"
    elif requires_ticket and category == "general_hr":
        disposition = "requires_hr_ticket"
    elif severity == "ready":
        disposition = "resolvable"
    else:
        disposition = "requires_hr_ticket"

    answer_payload: dict[str, Any] = {}
    if category == "leave_balance":
        answer_payload = dict(service_data.get("leave_balance") or {})
    elif category == "attendance":
        answer_payload = dict(service_data.get("attendance_summary") or {})
    elif category == "training":
        catalog = service_data.get("training_catalog") or {}
        answer_payload = {
            "courses": list(catalog.get("courses") or [])[:10],
            "count": catalog.get("count"),
        }
    elif category == "onboarding":
        tasks = service_data.get("onboarding_tasks") or {}
        answer_payload = {
            "tasks": tasks.get("tasks") or tasks.get("items") or tasks,
            "documents": service_data.get("onboarding_documents"),
        }
    elif category == "recruitment_status":
        answer_payload = dict(service_data.get("candidate") or {})
    elif category in {"policy_information", "benefits"}:
        answer_payload = {
            "knowledge_hits": service_data.get("knowledge_hits") or [],
            "domain_knowledge_hits": service_data.get("domain_knowledge_hits") or [],
        }

    analysis = {
        "employee_id": employee_id or None,
        "candidate_id": request.get("candidate_id"),
        "category": category,
        "disposition": disposition,
        "requires_document": requires_document,
        "requires_hr_ticket": requires_ticket,
        "requires_approval": requires_approval,
        "requires_escalation": requires_escalation,
        "blocked": disposition == "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "service_data": service_data,
        "answer_payload": answer_payload,
        "document_type": request.get("document_type") or service_data.get("document_type"),
        "summary": request.get("summary") or state.get("user_request"),
        "route_hint": policy.get("route_hint") or "resolve",
        "policy_severity": severity,
        "approval_level": policy.get("approval_level"),
        "authorization": authorization,
        "recommendation": disposition,
    }

    _, memory_patch = append_short_term(
        state,
        agent="service_analysis",
        content=(
            f"HR services analysis category={category}; disposition={disposition}; "
            f"blocked={len(blockers)}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "service_analysis",
        f"Analyzed HR service category={category}; disposition={disposition}.",
        analysis_results=analysis,
        **combine_patches(*patches),
    )
