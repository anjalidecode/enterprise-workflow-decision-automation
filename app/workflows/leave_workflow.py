"""Leave & Attendance workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.action import action_agent
from app.agents.analysis import analysis_agent
from app.agents.decision import decision_agent
from app.agents.orchestrator import orchestrator_agent
from app.agents.planner import planner_agent
from app.agents.policy import policy_agent
from app.agents.research import research_agent
from app.agents.response import response_agent
from app.agents.validation import validation_agent
from app.orchestration.state import WorkflowState, create_initial_state

AGENT_NODES = (
    "orchestrator",
    "planner",
    "research",
    "policy",
    "analysis",
    "decision",
    "validation",
    "action",
    "response",
)


def route_after_validation(state: WorkflowState) -> Literal["action", "response"]:
    """Branch after validation: execute actions, or skip to the response."""

    route = (state.get("metadata") or {}).get("route", "response")
    if route == "action":
        return "action"
    return "response"


def build_leave_graph() -> StateGraph:
    """Construct the uncompiled leave workflow graph."""

    graph = StateGraph(WorkflowState)
    graph.add_node("orchestrator", orchestrator_agent)
    graph.add_node("planner", planner_agent)
    graph.add_node("research", research_agent)
    graph.add_node("policy", policy_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("decision", decision_agent)
    graph.add_node("validation", validation_agent)
    graph.add_node("action", action_agent)
    graph.add_node("response", response_agent)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "policy")
    graph.add_edge("policy", "analysis")
    graph.add_edge("analysis", "decision")
    graph.add_edge("decision", "validation")
    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "action": "action",
            "response": "response",
        },
    )
    graph.add_edge("action", "response")
    graph.add_edge("response", END)
    return graph


def build_leave_workflow() -> CompiledStateGraph:
    """Compile the leave & attendance workflow."""

    return build_leave_graph().compile()


def run_leave_workflow(user_request: str) -> WorkflowState:
    """Execute a leave workflow run and return the final shared state."""

    graph = build_leave_workflow()
    initial_state = create_initial_state(user_request)
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
