"""Service Decision: produce WorkflowDecision for HR services."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, recall_long_term, search_short_term
from app.models.decision import WorkflowDecision
from app.orchestration.state import WorkflowState


def build_hr_services_pending_actions(
    *,
    employee_id: str,
    category: str,
    analysis: dict[str, Any],
    rationale: str,
    include_approval_actions: bool = False,
) -> list[dict[str, Any]]:
    if not employee_id and category not in {"policy_information", "benefits", "training", "general_hr"}:
        return []

    actions: list[dict[str, Any]] = []
    summary = str(analysis.get("summary") or rationale)[:240]
    document_type = str(analysis.get("document_type") or "employment_certificate")
    disposition = str(analysis.get("disposition") or "")

    if disposition == "requires_document" or category == "employment_document":
        actions.append(
            {
                "type": "create_hr_document_request",
                "employee_id": employee_id,
                "document_type": document_type,
                "summary": summary,
            }
        )
    elif disposition in {"requires_hr_ticket", "requires_escalation"} or category in {
        "general_hr",
        "payroll_routing",
        "employee_profile",
    }:
        priority = "high" if category == "payroll_routing" else "normal"
        status = "open"
        actions.append(
            {
                "type": "create_hr_service_request",
                "employee_id": employee_id or "UNKNOWN",
                "category": category,
                "summary": summary,
                "priority": priority,
                "status": status,
            }
        )
        # route_to_hr needs request_id from create; action agent will chain after create.
        actions.append(
            {
                "type": "route_hr_service_to_hr",
                "request_id": "__from_create__",
                "reason": rationale[:200],
                "priority": priority,
            }
        )

    if include_approval_actions and category == "employee_profile" and employee_id:
        # After approval, create/update ticket and notify.
        if not any(item.get("type") == "create_hr_service_request" for item in actions):
            actions.append(
                {
                    "type": "create_hr_service_request",
                    "employee_id": employee_id,
                    "category": category,
                    "summary": summary,
                    "priority": "normal",
                    "status": "in_progress",
                }
            )
            actions.append(
                {
                    "type": "route_hr_service_to_hr",
                    "request_id": "__from_create__",
                    "reason": "Approved profile-change request.",
                    "priority": "normal",
                }
            )

    if employee_id and actions:
        actions.append(
            {
                "type": "notify_employee",
                "employee_id": employee_id,
                "message": f"HR services update ({category}): {rationale[:180]}",
            }
        )

    # Resolve-only paths may still notify when there is a concrete answer.
    if not actions and employee_id and disposition == "resolvable":
        actions.append(
            {
                "type": "notify_employee",
                "employee_id": employee_id,
                "message": f"HR services resolved your {category} request. {rationale[:180]}",
            }
        )

    return actions


def service_decision_agent(state: WorkflowState) -> dict[str, Any]:
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    employee = state.get("employee_data") or {}
    employee_id = str(
        analysis.get("employee_id")
        or employee.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    category = str(analysis.get("category") or policy.get("category") or "general_hr")
    patches: list[dict[str, Any]] = []

    _, notes_patch = search_short_term(state, agent="service_decision")
    patches.append(notes_patch)
    history, history_patch = recall_long_term(
        state,
        agent="service_decision",
        employee_id=employee_id or None,
        workflow_type="hr_services",
    )
    patches.append(history_patch)

    blockers = list(analysis.get("blockers") or policy.get("violations") or [])
    warnings = list(analysis.get("warnings") or policy.get("warnings") or [])
    evidence = [
        f"category={category}",
        f"disposition={analysis.get('disposition')}",
        f"severity={policy.get('severity')}",
        f"route_hint={policy.get('route_hint')}",
        f"auth_allowed={(analysis.get('authorization') or {}).get('allowed')}",
    ]
    if history:
        warnings.append("Prior HR service outcomes were available as context only.")

    disposition = str(analysis.get("disposition") or "")
    pending_actions: list[dict[str, Any]] = []
    route_hint = str(policy.get("route_hint") or analysis.get("route_hint") or "resolve")

    if disposition == "blocked" or blockers:
        outcome = "blocked"
        executable = False
        requires_human_approval = False
        confidence = 0.95
        rationale = (
            "HR service request is blocked due to authorization or policy violations: "
            + ("; ".join(str(item) for item in blockers) if blockers else "insufficient data.")
        )
        route_hint = "escalate"
    elif disposition == "requires_approval" or (
        policy.get("requires_human_approval") and category == "employee_profile"
    ):
        outcome = "pending_approval"
        executable = False
        requires_human_approval = True
        confidence = 0.9
        rationale = (
            f"Profile/HR change for {employee_id or 'employee'} requires human approval "
            f"(approval_level={policy.get('approval_level') or 'hr'}). "
            "No sensitive profile fields were changed automatically."
        )
        pending_actions = [
            {
                "type": "request_human_approval",
                "employee_id": employee_id,
                "approval_level": policy.get("approval_level") or "hr",
                "reason": "profile_change",
            }
        ]
        route_hint = "escalate"
    elif disposition == "requires_escalation" or str(policy.get("severity")) == "escalate":
        # Create/route an escalated ticket immediately; do not change payroll data.
        outcome = "ready"
        executable = True
        requires_human_approval = False
        confidence = 0.9
        rationale = (
            f"HR service category={category} requires escalation to HR/payroll support. "
            "A service ticket will be created and routed; no payroll data will be changed."
        )
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = build_hr_services_pending_actions(
            employee_id=employee_id,
            category=category,
            analysis=analysis,
            rationale=rationale,
        )
        route_hint = "create_ticket"
    elif disposition in {"requires_document", "requires_hr_ticket"} or route_hint == "create_ticket":
        outcome = "ready"
        executable = True
        requires_human_approval = False
        confidence = 0.9
        rationale = (
            f"HR service category={category} is ready for ticket/document handling "
            f"for {employee_id or 'requester'}."
        )
        pending_actions = build_hr_services_pending_actions(
            employee_id=employee_id,
            category=category,
            analysis=analysis,
            rationale=rationale,
        )
        route_hint = "create_ticket"
    elif disposition == "resolvable" or str(policy.get("severity")) == "ready":
        outcome = "ready"
        executable = True
        requires_human_approval = False
        confidence = 0.92
        answer = analysis.get("answer_payload") or {}
        if category == "leave_balance":
            rationale = (
                f"Leave balance for {employee_id}: "
                f"{answer.get('leave_type', 'annual')}={answer.get('balance', 'n/a')} days."
            )
        elif category == "attendance":
            rationale = (
                f"Attendance summary for {employee_id}: "
                f"present={answer.get('present_days', 'n/a')}, "
                f"absent={answer.get('absent_days', 'n/a')}, "
                f"late={answer.get('late_arrivals', 'n/a')}."
            )
        elif category == "training":
            rationale = (
                f"Training catalog results available "
                f"(count={answer.get('count', len(answer.get('courses') or []))})."
            )
        elif category == "onboarding":
            rationale = f"Onboarding status retrieved for {employee_id}."
        elif category == "recruitment_status":
            rationale = (
                f"Recruitment status for candidate "
                f"{analysis.get('candidate_id') or answer.get('candidate_id') or 'n/a'} retrieved."
            )
        elif category in {"policy_information", "benefits"}:
            hits = answer.get("knowledge_hits") or answer.get("domain_knowledge_hits") or []
            title = hits[0].get("title") if hits else "HR services handbook"
            rationale = f"Policy/benefits information provided from knowledge ({title})."
        else:
            rationale = f"HR service category={category} resolved automatically."
        if warnings:
            rationale += " " + "; ".join(str(item) for item in warnings)
        pending_actions = build_hr_services_pending_actions(
            employee_id=employee_id,
            category=category,
            analysis=analysis,
            rationale=rationale,
        )
        route_hint = "resolve"
    else:
        outcome = "recommend"
        executable = False
        requires_human_approval = False
        confidence = 0.8
        rationale = (
            f"HR service recommendations prepared for category={category}. "
            "No automated write actions scheduled."
        )
        route_hint = "escalate"

    decision = WorkflowDecision(
        outcome=outcome,  # type: ignore[arg-type]
        rationale=rationale,
        executable=executable,
        confidence=confidence,
        requires_human_approval=requires_human_approval,
        entity_refs={
            "employee_id": employee_id or None,
            "candidate_id": analysis.get("candidate_id"),
            "category": category,
            "disposition": disposition,
            "route_hint": route_hint,
            "approval_level": policy.get("approval_level"),
            "severity": policy.get("severity"),
        },
        evidence=evidence,
        blockers=blockers,
        warnings=warnings,
        influenced_by=[item.memory_id for item in history],
    )

    metadata = dict(state.get("metadata") or {})
    metadata["service_category"] = category
    metadata["service_disposition"] = disposition
    metadata["hr_services_route_hint"] = route_hint
    metadata["hr_services_severity"] = policy.get("severity")

    _, memory_patch = append_short_term(
        state,
        agent="service_decision",
        kind="influence",
        content=(
            f"Decision={decision.outcome}; executable={decision.executable}; "
            f"route={route_hint}; approval={decision.requires_human_approval}."
        ),
        influenced_decision=bool(history or warnings),
    )
    patches.append(memory_patch)

    return node_update(
        "service_decision",
        f"Decision={decision.outcome}; category={category}; route={route_hint}.",
        decision=decision.model_dump(),
        confidence=decision.confidence,
        pending_actions=pending_actions,
        requires_human_approval=requires_human_approval,
        metadata=metadata,
        **combine_patches(*patches),
    )
