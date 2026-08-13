"""Training workflow graph (LangGraph)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.training.action import training_action_agent
from app.agents.training.analysis import training_analysis_agent
from app.agents.training.catalog_research import training_catalog_research_agent
from app.agents.training.decision import training_decision_agent
from app.agents.training.employee_research import training_research_agent
from app.agents.training.planner import training_planner_agent
from app.agents.training.policy import training_policy_agent
from app.agents.training.response import training_response_agent
from app.agents.training.skill_gap_analysis import skill_gap_analysis_agent
from app.agents.training.validation import training_validation_agent
from app.memory.facade import reset_short_term_memory
from app.orchestration.state import WorkflowState, create_initial_state
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.services.performance_store import reset_performance_store
from app.services.training_store import reset_training_store

TRAINING_AGENT_NODES = (
    "training_planner",
    "training_research",
    "skill_gap_analysis",
    "training_catalog_research",
    "training_policy",
    "training_analysis",
    "training_decision",
    "training_validation",
    "training_action",
    "training_response",
)


def route_after_training_validation(
    state: WorkflowState,
) -> Literal["training_action", "training_response"]:
    route = (state.get("metadata") or {}).get("route", "response")
    if route == "action":
        return "training_action"
    return "training_response"


def build_training_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("training_planner", training_planner_agent)
    graph.add_node("training_research", training_research_agent)
    graph.add_node("skill_gap_analysis", skill_gap_analysis_agent)
    graph.add_node("training_catalog_research", training_catalog_research_agent)
    graph.add_node("training_policy", training_policy_agent)
    graph.add_node("training_analysis", training_analysis_agent)
    graph.add_node("training_decision", training_decision_agent)
    graph.add_node("training_validation", training_validation_agent)
    graph.add_node("training_action", training_action_agent)
    graph.add_node("training_response", training_response_agent)

    graph.add_edge(START, "training_planner")
    graph.add_edge("training_planner", "training_research")
    graph.add_edge("training_research", "skill_gap_analysis")
    graph.add_edge("skill_gap_analysis", "training_catalog_research")
    graph.add_edge("training_catalog_research", "training_policy")
    graph.add_edge("training_policy", "training_analysis")
    graph.add_edge("training_analysis", "training_decision")
    graph.add_edge("training_decision", "training_validation")
    graph.add_conditional_edges(
        "training_validation",
        route_after_training_validation,
        {
            "training_action": "training_action",
            "training_response": "training_response",
        },
    )
    graph.add_edge("training_action", "training_response")
    graph.add_edge("training_response", END)
    return graph


def build_training_workflow() -> CompiledStateGraph:
    return build_training_graph().compile()


def run_training_workflow(
    user_request: str,
    *,
    reset_runtime: bool = True,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "training",
) -> WorkflowState:
    """Execute the training workflow and return final shared state."""

    reset_short_term_memory()
    if reset_runtime:
        reset_hr_store()
        reset_performance_store()
        reset_training_store()
        reset_notification_service()
    graph = build_training_workflow()
    initial_state = create_initial_state(
        user_request,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by,
        user_role=user_role,
        request_id=request_id,
        entities=entities,
        workflow_type=workflow_type or "training",
    )
    result = graph.invoke(initial_state)
    return result  # type: ignore[return-value]
