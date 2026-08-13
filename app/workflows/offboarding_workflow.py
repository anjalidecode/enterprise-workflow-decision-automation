"""Offboarding workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.offboarding.action import offboarding_action_agent
from app.agents.offboarding.analysis import offboarding_analysis_agent
from app.agents.offboarding.checklist_analysis import checklist_analysis_agent
from app.agents.offboarding.decision import offboarding_decision_agent
from app.agents.offboarding.employee_research import offboarding_employee_research_agent
from app.agents.offboarding.exit_details_research import exit_details_research_agent
from app.agents.offboarding.planner import offboarding_planner_agent
from app.agents.offboarding.policy import offboarding_policy_agent
from app.agents.offboarding.response import offboarding_response_agent
from app.agents.offboarding.validation import offboarding_validation_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.services.offboarding_store import reset_offboarding_store

OFFBOARDING_AGENT_NODES = (
    "offboarding_planner",
    "offboarding_employee_research",
    "exit_details_research",
    "checklist_analysis",
    "offboarding_policy",
    "offboarding_analysis",
    "offboarding_decision",
    "offboarding_validation",
    "offboarding_action",
    "offboarding_response",
)


def route_after_offboarding_validation(
    state: WorkflowState,
) -> Literal["offboarding_action", "offboarding_response"]:
    """Route ready → action; blocked/review → response."""

    route = (state.get("metadata") or {}).get("route", "response")
    if route == "action":
        return "offboarding_action"
    return "offboarding_response"


def build_offboarding_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("offboarding_planner", offboarding_planner_agent)
    graph.add_node("offboarding_employee_research", offboarding_employee_research_agent)
    graph.add_node("exit_details_research", exit_details_research_agent)
    graph.add_node("checklist_analysis", checklist_analysis_agent)
    graph.add_node("offboarding_policy", offboarding_policy_agent)
    graph.add_node("offboarding_analysis", offboarding_analysis_agent)
    graph.add_node("offboarding_decision", offboarding_decision_agent)
    graph.add_node("offboarding_validation", offboarding_validation_agent)
    graph.add_node("offboarding_action", offboarding_action_agent)
    graph.add_node("offboarding_response", offboarding_response_agent)

    graph.add_edge(START, "offboarding_planner")
    graph.add_edge("offboarding_planner", "offboarding_employee_research")
    graph.add_edge("offboarding_employee_research", "exit_details_research")
    graph.add_edge("exit_details_research", "checklist_analysis")
    graph.add_edge("checklist_analysis", "offboarding_policy")
    graph.add_edge("offboarding_policy", "offboarding_analysis")
    graph.add_edge("offboarding_analysis", "offboarding_decision")
    graph.add_edge("offboarding_decision", "offboarding_validation")
    graph.add_conditional_edges(
        "offboarding_validation",
        route_after_offboarding_validation,
        {
            "offboarding_action": "offboarding_action",
            "offboarding_response": "offboarding_response",
        },
    )
    graph.add_edge("offboarding_action", "offboarding_response")
    graph.add_edge("offboarding_response", END)
    return graph


def build_offboarding_workflow() -> CompiledStateGraph:
    return build_offboarding_graph().compile()


def run_offboarding_workflow(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "offboarding",
) -> WorkflowState:
    """Execute the offboarding workflow and return final shared state."""

    reset_short_term_memory()
    if reset_runtime:
        reset_hr_store()
        reset_offboarding_store()
        reset_notification_service()
    graph = build_offboarding_workflow()
    initial_state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type or "offboarding",
    )
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
