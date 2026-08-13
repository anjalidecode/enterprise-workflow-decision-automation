"""Employee HR Services workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.hr_services.employee_context import employee_context_agent
from app.agents.hr_services.planner import hr_services_planner_agent
from app.agents.hr_services.request_classification import request_classification_agent
from app.agents.hr_services.service_action import service_action_agent
from app.agents.hr_services.service_analysis import service_analysis_agent
from app.agents.hr_services.service_decision import service_decision_agent
from app.agents.hr_services.service_policy import service_policy_agent
from app.agents.hr_services.service_research import service_research_agent
from app.agents.hr_services.service_response import service_response_agent
from app.agents.hr_services.service_validation import service_validation_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.services.attendance_store import reset_attendance_store
from app.services.hr_services_store import reset_hr_services_store
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.services.onboarding_store import reset_onboarding_store
from app.services.recruitment_store import reset_recruitment_store
from app.services.training_store import reset_training_store

HR_SERVICES_AGENT_NODES = (
    "hr_services_planner",
    "request_classification",
    "employee_context",
    "service_research",
    "service_policy",
    "service_analysis",
    "service_decision",
    "service_validation",
    "service_action",
    "service_response",
)


def route_after_hr_services_validation(
    state: WorkflowState,
) -> Literal["resolve", "create_ticket", "escalate"]:
    """Route ready resolve / ticket creation / escalate-or-response."""

    route = (state.get("metadata") or {}).get("route", "escalate")
    if route == "resolve":
        return "resolve"
    if route == "create_ticket":
        return "create_ticket"
    return "escalate"


def build_hr_services_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("hr_services_planner", hr_services_planner_agent)
    graph.add_node("request_classification", request_classification_agent)
    graph.add_node("employee_context", employee_context_agent)
    graph.add_node("service_research", service_research_agent)
    graph.add_node("service_policy", service_policy_agent)
    graph.add_node("service_analysis", service_analysis_agent)
    graph.add_node("service_decision", service_decision_agent)
    graph.add_node("service_validation", service_validation_agent)
    graph.add_node("service_action", service_action_agent)
    graph.add_node("service_response", service_response_agent)

    graph.add_edge(START, "hr_services_planner")
    graph.add_edge("hr_services_planner", "request_classification")
    graph.add_edge("request_classification", "employee_context")
    graph.add_edge("employee_context", "service_research")
    graph.add_edge("service_research", "service_policy")
    graph.add_edge("service_policy", "service_analysis")
    graph.add_edge("service_analysis", "service_decision")
    graph.add_edge("service_decision", "service_validation")
    graph.add_conditional_edges(
        "service_validation",
        route_after_hr_services_validation,
        {
            # resolve and create_ticket both execute through service_action
            "resolve": "service_action",
            "create_ticket": "service_action",
            "escalate": "service_response",
        },
    )
    graph.add_edge("service_action", "service_response")
    graph.add_edge("service_response", END)
    return graph


def build_hr_services_workflow() -> CompiledStateGraph:
    return build_hr_services_graph().compile()


def run_hr_services_workflow(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "hr_services",
) -> WorkflowState:
    """Execute the HR services workflow and return final shared state."""

    reset_short_term_memory()
    if reset_runtime:
        reset_hr_store()
        reset_hr_services_store()
        reset_attendance_store()
        reset_training_store()
        reset_onboarding_store()
        reset_recruitment_store()
        reset_notification_service()
    graph = build_hr_services_workflow()
    initial_state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type or "hr_services",
    )
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
