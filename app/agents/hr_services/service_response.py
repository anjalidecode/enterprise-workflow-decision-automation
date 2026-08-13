"""Service Response: professional response with evidence and next steps."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_knowledge, search_short_term, write_long_term
from app.orchestration.state import WorkflowState


def service_response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    employee = state.get("employee_data") or {}
    analysis = state.get("analysis_results") or {}
    policy = state.get("policy_results") or {}
    completed = list(state.get("completed_actions") or [])
    patches: list[dict[str, Any]] = []

    notes, notes_patch = search_short_term(state, agent="service_response")
    patches.append(notes_patch)
    hits, knowledge_patch = search_knowledge(
        state,
        agent="service_response",
        query="hr support document request escalation confidentiality",
        workflow_type="hr_services",
    )
    patches.append(knowledge_patch)

    status = state.get("status") or "completed"
    if status == "awaiting_human_approval":
        final_status = "awaiting_human_approval"
    elif status == "validation_failed":
        final_status = "validation_failed"
    else:
        final_status = "completed"

    handbook = hits[0].title if hits else "HR services handbook"
    category = str(analysis.get("category") or policy.get("category") or "general_hr")
    employee_label = (
        f"{employee.get('name') or 'Unknown'} "
        f"({employee.get('employee_id') or analysis.get('employee_id') or 'n/a'})"
    )
    outcome = decision.get("outcome")
    blockers = decision.get("blockers") or analysis.get("blockers") or []
    warnings = decision.get("warnings") or analysis.get("warnings") or []
    answer = analysis.get("answer_payload") or {}
    branch = (state.get("metadata") or {}).get("decision_branch") or "response"

    tickets = [
        item
        for item in completed
        if item.get("type") in {"create_hr_service_request", "create_hr_document_request"}
    ]
    routes = [item for item in completed if item.get("type") == "route_hr_service_to_hr"]
    notifications = [item for item in completed if item.get("type") == "notify_employee"]
    ticket_ids = [
        str(item.get("request_id") or item.get("document_request_id") or "")
        for item in tickets
        if item.get("request_id") or item.get("document_request_id")
    ]
    ticket_note = ", ".join(ticket_ids) if ticket_ids else "none"

    def _answer_text() -> str:
        if category == "leave_balance" and answer:
            return (
                f"{answer.get('leave_type', 'annual')} leave balance="
                f"{answer.get('balance', 'n/a')} "
                f"(source={answer.get('source', 'tool')})."
            )
        if category == "attendance" and answer:
            return (
                f"present={answer.get('present_days', 'n/a')}, "
                f"absent={answer.get('absent_days', 'n/a')}, "
                f"late={answer.get('late_arrivals', 'n/a')}, "
                f"attendance%={answer.get('attendance_percentage', 'n/a')}."
            )
        if category == "training":
            courses = answer.get("courses") or []
            titles = [
                str(item.get("title") or item.get("course_id") or item)
                for item in courses[:5]
            ]
            return f"Available programs: {', '.join(titles) or 'none listed'}."
        if category == "onboarding":
            return f"Onboarding task/document status retrieved for {employee_label}."
        if category == "recruitment_status" and answer:
            return (
                f"Candidate {answer.get('candidate_id') or analysis.get('candidate_id')}: "
                f"status={answer.get('status') or answer.get('stage') or 'retrieved'}."
            )
        if category in {"policy_information", "benefits"}:
            hits_local = answer.get("domain_knowledge_hits") or answer.get("knowledge_hits") or []
            if hits_local:
                return f"{hits_local[0].get('title')}: {hits_local[0].get('snippet', '')[:180]}"
            return f"See curated knowledge ({handbook})."
        return str(decision.get("rationale") or "No automated answer body.")

    if final_status == "awaiting_human_approval":
        response = (
            f"HR Services request ({category}) for {employee_label} requires human approval. "
            f"Approval status: pending. Branch: {branch}. "
            f"No sensitive profile/payroll changes were executed. "
            f"Reason: {decision.get('rationale')}. Handbook: {handbook}."
        )
    elif outcome == "blocked":
        response = (
            f"HR Services request ({category}) for {employee_label} is blocked. "
            f"Blockers: {'; '.join(str(item) for item in blockers) or 'none'}. "
            f"No write actions were executed. Handbook: {handbook}."
        )
    elif outcome == "recommend":
        response = (
            f"HR Services recommendations ({category}) for {employee_label}. "
            f"Answer/result: {_answer_text()} "
            f"No automated write actions were executed. Handbook: {handbook}."
        )
    else:
        evidence = "tools"
        if category in {"policy_information", "benefits"}:
            evidence = "KnowledgeStore + policy"
        elif category == "leave_balance":
            evidence = "get_leave_balance"
        elif category == "attendance":
            evidence = "attendance tools"
        elif category == "training":
            evidence = "training catalog tools"
        elif category == "onboarding":
            evidence = "onboarding tools"
        elif category == "recruitment_status":
            evidence = "recruitment tools"

        next_steps = "No further action required."
        if tickets:
            next_steps = "Track the service ticket with HR; you will be notified on updates."
        if category == "payroll_routing":
            next_steps = "HR/payroll will review the escalated ticket; salary was not changed."
        if category == "employment_document":
            next_steps = "Document request recorded; HR will fulfill the simulated certificate."

        response = (
            f"HR Services ({category}) completed for {employee_label}. "
            f"Answer/result: {_answer_text()} "
            f"Evidence/source: {evidence}. "
            f"Ticket number(s): {ticket_note}. "
            f"Approval status: {outcome}. "
            f"Actions confirmed by tools: tickets={len(tickets)}, "
            f"routes={len(routes)}, notifications={len(notifications)}. "
            f"Branch: {branch}. "
            f"Warnings: {'; '.join(str(item).rstrip('.') for item in warnings) or 'none'}. "
            f"Next steps: {next_steps} Handbook: {handbook}."
        )

    try:
        if employee.get("employee_id") or analysis.get("employee_id") or category:
            _, ltm_patch = write_long_term(
                state,
                agent="service_response",
                payload={
                    "employee_id": str(
                        employee.get("employee_id") or analysis.get("employee_id") or "EMP"
                    ),
                    "workflow_type": "hr_services",
                    "outcome": outcome,
                    "category": category,
                    "ticket_ids": ticket_ids[:5],
                    "branch": branch,
                    "rationale_summary": str(decision.get("rationale") or "")[:400],
                    "requires_human_approval": bool(state.get("requires_human_approval")),
                },
            )
            patches.append(ltm_patch)
    except Exception:
        pass

    return node_update(
        "service_response",
        f"Composed HR services response; status={final_status}; notes={len(notes)}.",
        final_response=response,
        status=final_status,
        **combine_patches(*patches),
    )
