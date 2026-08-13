"""Performance workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.performance.action import performance_action_agent
from app.agents.performance.analysis import performance_analysis_agent
from app.agents.performance.decision import performance_decision_agent
from app.agents.performance.goal_analysis import goal_analysis_agent
from app.agents.performance.planner import performance_planner_agent
from app.agents.performance.policy import performance_policy_agent
from app.agents.performance.research import performance_research_agent
from app.agents.performance.response import performance_response_agent
from app.agents.performance.validation import performance_validation_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.services.performance_store import reset_performance_store

PERFORMANCE_AGENT_NODES = (
    "performance_planner",
    "performance_research",
    "goal_analysis",
    "performance_analysis",
    "performance_policy",
    "performance_decision",
    "performance_validation",
    "performance_action",
    "performance_response",
)


def route_after_performance_validation(
    state: WorkflowState,
) -> Literal["performance_action", "performance_response"]:
    route = (state.get("metadata") or {}).get("route", "response")
    if route == "action":
        return "performance_action"
    return "performance_response"


def build_performance_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("performance_planner", performance_planner_agent)
    graph.add_node("performance_research", performance_research_agent)
    graph.add_node("goal_analysis", goal_analysis_agent)
    graph.add_node("performance_analysis", performance_analysis_agent)
    graph.add_node("performance_policy", performance_policy_agent)
    graph.add_node("performance_decision", performance_decision_agent)
    graph.add_node("performance_validation", performance_validation_agent)
    graph.add_node("performance_action", performance_action_agent)
    graph.add_node("performance_response", performance_response_agent)

    graph.add_edge(START, "performance_planner")
    graph.add_edge("performance_planner", "performance_research")
    graph.add_edge("performance_research", "goal_analysis")
    graph.add_edge("goal_analysis", "performance_analysis")
    graph.add_edge("performance_analysis", "performance_policy")
    graph.add_edge("performance_policy", "performance_decision")
    graph.add_edge("performance_decision", "performance_validation")
    graph.add_conditional_edges(
        "performance_validation",
        route_after_performance_validation,
        {
            "performance_action": "performance_action",
            "performance_response": "performance_response",
        },
    )
    graph.add_edge("performance_action", "performance_response")
    graph.add_edge("performance_response", END)
    return graph


def build_performance_workflow() -> CompiledStateGraph:
    return build_performance_graph().compile()


def run_performance_workflow(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "performance",
) -> WorkflowState:
    """Execute the performance workflow and return final shared state."""

    reset_short_term_memory()
    if reset_runtime:
        reset_hr_store()
        reset_performance_store()
        reset_notification_service()
    graph = build_performance_workflow()
    initial_state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type or "performance",
    )
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
