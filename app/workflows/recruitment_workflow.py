"""Recruitment workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.recruitment.action import recruitment_action_agent
from app.agents.recruitment.analysis import candidate_analysis_agent
from app.agents.recruitment.decision import recruitment_decision_agent
from app.agents.recruitment.job_research import job_research_agent
from app.agents.recruitment.planner import recruitment_planner_agent
from app.agents.recruitment.policy import recruitment_policy_agent
from app.agents.recruitment.research import candidate_research_agent
from app.agents.recruitment.response import recruitment_response_agent
from app.agents.recruitment.scoring import candidate_scoring_agent
from app.agents.recruitment.validation import recruitment_validation_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.services.notifications import reset_notification_service
from app.services.recruitment_store import reset_recruitment_store

RECRUITMENT_AGENT_NODES = (
    "recruitment_planner",
    "job_research",
    "candidate_research",
    "candidate_analysis",
    "candidate_scoring",
    "recruitment_policy",
    "recruitment_decision",
    "recruitment_validation",
    "recruitment_action",
    "recruitment_response",
)


def route_after_recruitment_validation(
    state: WorkflowState,
) -> Literal["recruitment_action", "recruitment_response"]:
    route = (state.get("metadata") or {}).get("route", "response")
    if route == "action":
        return "recruitment_action"
    return "recruitment_response"


def build_recruitment_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("recruitment_planner", recruitment_planner_agent)
    graph.add_node("job_research", job_research_agent)
    graph.add_node("candidate_research", candidate_research_agent)
    graph.add_node("candidate_analysis", candidate_analysis_agent)
    graph.add_node("candidate_scoring", candidate_scoring_agent)
    graph.add_node("recruitment_policy", recruitment_policy_agent)
    graph.add_node("recruitment_decision", recruitment_decision_agent)
    graph.add_node("recruitment_validation", recruitment_validation_agent)
    graph.add_node("recruitment_action", recruitment_action_agent)
    graph.add_node("recruitment_response", recruitment_response_agent)

    graph.add_edge(START, "recruitment_planner")
    graph.add_edge("recruitment_planner", "job_research")
    graph.add_edge("job_research", "candidate_research")
    graph.add_edge("candidate_research", "candidate_analysis")
    graph.add_edge("candidate_analysis", "candidate_scoring")
    graph.add_edge("candidate_scoring", "recruitment_policy")
    graph.add_edge("recruitment_policy", "recruitment_decision")
    graph.add_edge("recruitment_decision", "recruitment_validation")
    graph.add_conditional_edges(
        "recruitment_validation",
        route_after_recruitment_validation,
        {
            "recruitment_action": "recruitment_action",
            "recruitment_response": "recruitment_response",
        },
    )
    graph.add_edge("recruitment_action", "recruitment_response")
    graph.add_edge("recruitment_response", END)
    return graph


def build_recruitment_workflow() -> CompiledStateGraph:
    return build_recruitment_graph().compile()


def run_recruitment_workflow(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "recruitment",
) -> WorkflowState:
    """Execute the recruitment workflow and return final shared state."""

    reset_short_term_memory()
    if reset_runtime:
        reset_recruitment_store()
        reset_notification_service()
    graph = build_recruitment_workflow()
    initial_state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type or "recruitment",
    )
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
