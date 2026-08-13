"""Employee Onboarding workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.onboarding.action import onboarding_action_agent
from app.agents.onboarding.analysis import onboarding_analysis_agent
from app.agents.onboarding.decision import onboarding_decision_agent
from app.agents.onboarding.document_verification import document_verification_agent
from app.agents.onboarding.employee_research import employee_research_agent
from app.agents.onboarding.planner import onboarding_planner_agent
from app.agents.onboarding.policy import onboarding_policy_agent
from app.agents.onboarding.response import onboarding_response_agent
from app.agents.onboarding.validation import onboarding_validation_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.services.onboarding_store import reset_onboarding_store

ONBOARDING_AGENT_NODES = (
    "onboarding_planner",
    "employee_research",
    "document_verification",
    "onboarding_policy",
    "onboarding_analysis",
    "onboarding_decision",
    "onboarding_validation",
    "onboarding_action",
    "onboarding_response",
)


def route_after_onboarding_validation(
    state: WorkflowState,
) -> Literal["onboarding_action", "onboarding_response"]:
    route = (state.get("metadata") or {}).get("route", "response")
    if route == "action":
        return "onboarding_action"
    return "onboarding_response"


def build_onboarding_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("onboarding_planner", onboarding_planner_agent)
    graph.add_node("employee_research", employee_research_agent)
    graph.add_node("document_verification", document_verification_agent)
    graph.add_node("onboarding_policy", onboarding_policy_agent)
    graph.add_node("onboarding_analysis", onboarding_analysis_agent)
    graph.add_node("onboarding_decision", onboarding_decision_agent)
    graph.add_node("onboarding_validation", onboarding_validation_agent)
    graph.add_node("onboarding_action", onboarding_action_agent)
    graph.add_node("onboarding_response", onboarding_response_agent)

    graph.add_edge(START, "onboarding_planner")
    graph.add_edge("onboarding_planner", "employee_research")
    graph.add_edge("employee_research", "document_verification")
    graph.add_edge("document_verification", "onboarding_policy")
    graph.add_edge("onboarding_policy", "onboarding_analysis")
    graph.add_edge("onboarding_analysis", "onboarding_decision")
    graph.add_edge("onboarding_decision", "onboarding_validation")
    graph.add_conditional_edges(
        "onboarding_validation",
        route_after_onboarding_validation,
        {
            "onboarding_action": "onboarding_action",
            "onboarding_response": "onboarding_response",
        },
    )
    graph.add_edge("onboarding_action", "onboarding_response")
    graph.add_edge("onboarding_response", END)
    return graph


def build_onboarding_workflow() -> CompiledStateGraph:
    return build_onboarding_graph().compile()


def run_onboarding_workflow(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "onboarding",
) -> WorkflowState:
    """Execute the onboarding workflow and return final shared state."""

    reset_short_term_memory()
    if reset_runtime:
        reset_hr_store()
        reset_onboarding_store()
        reset_notification_service()
    graph = build_onboarding_workflow()
    initial_state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type or "onboarding",
    )
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
