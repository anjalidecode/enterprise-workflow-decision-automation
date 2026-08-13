"""Service Research: retrieve authoritative info by reusing existing domain tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term, search_knowledge
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def service_research_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("hr_services_request") or {}
    authorization = (state.get("metadata") or {}).get("authorization") or (
        (state.get("retrieved_data") or {}).get("authorization") or {}
    )
    category = str(request.get("category") or "general_hr")
    employee = state.get("employee_data") or {}
    employee_id = str(
        employee.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    candidate_id = str(
        request.get("candidate_id") or (state.get("entities") or {}).get("candidate_id") or ""
    )
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    service_data: dict[str, Any] = {
        "category": category,
        "employee_id": employee_id or None,
        "candidate_id": candidate_id or None,
    }

    # Do not pull sensitive domain data when authorization already failed.
    if authorization.get("disclosure_blocked") and not authorization.get("allowed", True):
        service_data["blocked_reason"] = authorization.get("reason")
        _, memory_patch = append_short_term(
            state,
            agent="service_research",
            content=f"Skipped sensitive research for {category}; disclosure blocked.",
        )
        return node_update(
            "service_research",
            f"Skipped research for blocked {category} request.",
            retrieved_data={**(state.get("retrieved_data") or {}), "service_data": service_data},
            errors=errors,
            **combine_patches(memory_patch),
        )

    if category == "leave_balance" and employee_id:
        leave_type = str(request.get("leave_type") or "annual")
        result, patch = invoke_tool(
            state,
            agent="service_research",
            name="get_leave_balance",
            payload={"employee_id": employee_id, "leave_type": leave_type},
        )
        patches.append(patch)
        if result.success and result.data:
            service_data["leave_balance"] = result.data
        else:
            service_data["leave_balance_error"] = result.error_message or "leave balance lookup failed"
            errors.append(service_data["leave_balance_error"])

    elif category == "attendance" and employee_id:
        start_date = str(request.get("start_date") or "2026-07-01")
        end_date = str(request.get("end_date") or "2026-07-31")
        records_result, records_patch = invoke_tool(
            state,
            agent="service_research",
            name="get_attendance_records",
            payload={
                "employee_id": employee_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        patches.append(records_patch)
        records = []
        if records_result.success and records_result.data:
            records = list(records_result.data.get("records") or [])
            service_data["attendance_records"] = records_result.data
        else:
            errors.append(records_result.error_message or "attendance records lookup failed")

        summary_result, summary_patch = invoke_tool(
            state,
            agent="service_research",
            name="calculate_attendance_summary",
            payload={
                "employee_id": employee_id,
                "start_date": start_date,
                "end_date": end_date,
                "records": records,
            },
        )
        patches.append(summary_patch)
        if summary_result.success and summary_result.data:
            service_data["attendance_summary"] = summary_result.data
        else:
            errors.append(summary_result.error_message or "attendance summary failed")

    elif category == "training":
        result, patch = invoke_tool(
            state,
            agent="service_research",
            name="search_training_catalog",
            payload={"query": "training", "skill": ""},
        )
        patches.append(patch)
        if result.success and result.data:
            service_data["training_catalog"] = result.data
        else:
            errors.append(result.error_message or "training catalog search failed")
        if employee_id:
            hist_result, hist_patch = invoke_tool(
                state,
                agent="service_research",
                name="get_training_history",
                payload={"employee_id": employee_id},
            )
            patches.append(hist_patch)
            if hist_result.success and hist_result.data:
                service_data["training_history"] = hist_result.data

    elif category == "onboarding" and employee_id:
        tasks_result, tasks_patch = invoke_tool(
            state,
            agent="service_research",
            name="list_onboarding_tasks",
            payload={"employee_id": employee_id},
        )
        patches.append(tasks_patch)
        if tasks_result.success and tasks_result.data:
            service_data["onboarding_tasks"] = tasks_result.data
        else:
            errors.append(tasks_result.error_message or "onboarding tasks lookup failed")

        docs_result, docs_patch = invoke_tool(
            state,
            agent="service_research",
            name="get_employee_documents",
            payload={"employee_id": employee_id},
        )
        patches.append(docs_patch)
        if docs_result.success and docs_result.data:
            service_data["onboarding_documents"] = docs_result.data

    elif category == "recruitment_status" and candidate_id:
        result, patch = invoke_tool(
            state,
            agent="service_research",
            name="get_candidate",
            payload={"candidate_id": candidate_id},
        )
        patches.append(patch)
        if result.success and result.data:
            service_data["candidate"] = result.data
        else:
            errors.append(result.error_message or "candidate lookup failed")

    elif category in {"policy_information", "benefits"}:
        query = (
            "benefits information enrollment"
            if category == "benefits"
            else str(request.get("query") or "hr policy")
        )
        hits, knowledge_patch = search_knowledge(
            state,
            agent="service_research",
            query=query,
            workflow_type="hr_services",
        )
        patches.append(knowledge_patch)
        service_data["knowledge_hits"] = [
            {"title": item.title, "snippet": (item.content or "")[:240]}
            for item in hits[:5]
        ]
        # Also search leave/attendance knowledge for policy questions.
        if "attendance" in str(request.get("query") or "").lower():
            att_hits, att_patch = search_knowledge(
                state,
                agent="service_research",
                query="attendance policy",
                workflow_type="attendance",
            )
            patches.append(att_patch)
            service_data["domain_knowledge_hits"] = [
                {"title": item.title, "snippet": (item.content or "")[:240]}
                for item in att_hits[:5]
            ]
        elif "leave" in str(request.get("query") or "").lower():
            leave_hits, leave_patch = search_knowledge(
                state,
                agent="service_research",
                query="leave policy",
                workflow_type="leave_attendance",
            )
            patches.append(leave_patch)
            service_data["domain_knowledge_hits"] = [
                {"title": item.title, "snippet": (item.content or "")[:240]}
                for item in leave_hits[:5]
            ]

    elif category == "employment_document":
        service_data["document_type"] = request.get("document_type") or "employment_certificate"

    elif category in {"employee_profile", "payroll_routing", "general_hr"}:
        service_data["ticket_recommended"] = True
        service_data["summary"] = request.get("summary") or state.get("user_request")

    _, memory_patch = append_short_term(
        state,
        agent="service_research",
        content=f"Service research completed for category={category}; keys={list(service_data.keys())}.",
    )
    patches.append(memory_patch)

    return node_update(
        "service_research",
        f"Retrieved service data for category={category}.",
        retrieved_data={**(state.get("retrieved_data") or {}), "service_data": service_data},
        errors=errors,
        **combine_patches(*patches),
    )
