"""Attendance workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.attendance.action import attendance_action_agent
from app.agents.attendance.analysis import attendance_analysis_agent
from app.agents.attendance.decision import attendance_decision_agent
from app.agents.attendance.planner import attendance_planner_agent
from app.agents.attendance.policy import attendance_policy_agent
from app.agents.attendance.research import attendance_research_agent
from app.agents.attendance.response import attendance_response_agent
from app.agents.attendance.validation import attendance_validation_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.services.attendance_store import reset_attendance_store
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service

ATTENDANCE_AGENT_NODES = (
    "attendance_planner",
    "attendance_research",
    "attendance_analysis",
    "attendance_policy",
    "attendance_decision",
    "attendance_validation",
    "attendance_action",
    "attendance_response",
)


def route_after_attendance_validation(
    state: WorkflowState,
) -> Literal["attendance_action", "attendance_response"]:
    route = (state.get("metadata") or {}).get("route", "response")
    if route == "action":
        return "attendance_action"
    return "attendance_response"


def build_attendance_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("attendance_planner", attendance_planner_agent)
    graph.add_node("attendance_research", attendance_research_agent)
    graph.add_node("attendance_analysis", attendance_analysis_agent)
    graph.add_node("attendance_policy", attendance_policy_agent)
    graph.add_node("attendance_decision", attendance_decision_agent)
    graph.add_node("attendance_validation", attendance_validation_agent)
    graph.add_node("attendance_action", attendance_action_agent)
    graph.add_node("attendance_response", attendance_response_agent)

    graph.add_edge(START, "attendance_planner")
    graph.add_edge("attendance_planner", "attendance_research")
    graph.add_edge("attendance_research", "attendance_analysis")
    graph.add_edge("attendance_analysis", "attendance_policy")
    graph.add_edge("attendance_policy", "attendance_decision")
    graph.add_edge("attendance_decision", "attendance_validation")
    graph.add_conditional_edges(
        "attendance_validation",
        route_after_attendance_validation,
        {
            "attendance_action": "attendance_action",
            "attendance_response": "attendance_response",
        },
    )
    graph.add_edge("attendance_action", "attendance_response")
    graph.add_edge("attendance_response", END)
    return graph


def build_attendance_workflow() -> CompiledStateGraph:
    return build_attendance_graph().compile()


def run_attendance_workflow(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "attendance",
) -> WorkflowState:
    """Execute the attendance workflow and return final shared state."""

    reset_short_term_memory()
    if reset_runtime:
        reset_hr_store()
        reset_attendance_store()
        reset_notification_service()
    graph = build_attendance_workflow()
    initial_state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type or "attendance",
    )
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
