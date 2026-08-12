"""Recruitment workflow tests."""

from __future__ import annotations

import pytest

from app.services.recruitment_store import get_recruitment_store, reset_recruitment_store
from app.tools.catalog import get_registry
from app.workflows.contracts import ApprovalDecision
from app.workflows.engine import get_workflow_engine
from app.workflows.recruitment_workflow import (
    RECRUITMENT_AGENT_NODES,
    build_recruitment_graph,
    run_recruitment_workflow,
)
from app.workflows.registry import get_workflow_registry
from app.workflows.router import WorkflowRouter
from app.orchestration.state import create_initial_state

PYTHON_REQUEST = "Find candidates for the Python Backend Developer position."
J001_REQUEST = "Shortlist candidates for job J001."


def _agent_names(state: dict) -> list[str]:
    return [item["agent"] for item in state.get("agent_outputs") or []]


def _tool_names(state: dict) -> list[str]:
    return [item["tool_name"] for item in state.get("tool_executions") or []]


def test_recruitment_registration() -> None:
    registry = get_workflow_registry()
    spec = registry.get_spec("recruitment")
    assert spec.workflow_type == "recruitment"
    assert "candidate" in " ".join(spec.supported_request_hints)


def test_router_detects_recruitment() -> None:
    result = WorkflowRouter().classify(PYTHON_REQUEST)
    assert result.status == "routed"
    assert result.workflow_type == "recruitment"


def test_explicit_recruitment_selection() -> None:
    result = WorkflowRouter().classify(
        "Please process this HR case.",
        workflow_type="recruitment",
    )
    assert result.workflow_type == "recruitment"
    assert result.confidence == 1.0


def test_recruitment_graph_has_specialized_nodes_and_branch() -> None:
    graph = build_recruitment_graph()
    for name in RECRUITMENT_AGENT_NODES:
        assert name in graph.nodes
    assert "recruitment_validation" in graph.branches


def test_job_lookup_and_candidate_retrieval_via_engine() -> None:
    result = get_workflow_engine().run(PYTHON_REQUEST)
    state = result.state
    assert state["workflow_type"] == "recruitment"
    job = (state.get("retrieved_data") or {}).get("job") or {}
    assert job.get("job_id") == "J001"
    assert (state.get("retrieved_data") or {}).get("candidate_count", 0) >= 5
    assert "get_job" in _tool_names(state) or "search_jobs" in _tool_names(state)
    assert "search_candidates" in _tool_names(state)


def test_candidate_scoring_and_classifications() -> None:
    state = run_recruitment_workflow(J001_REQUEST)
    scores = {
        item["candidate_id"]: float(item["score"])
        for item in (state.get("analysis_results") or {}).get("candidate_scores") or []
    }
    assert scores["C001"] >= 75
    assert scores["C003"] < 55
    classifications = {
        item["candidate_id"]: item["label"]
        for item in (state.get("analysis_results") or {}).get("candidate_classifications") or []
    }
    assert classifications["C001"] == "shortlist"
    assert classifications["C003"] == "reject"
    assert classifications["C004"] == "review"
    assert "C002" in classifications


def test_strong_candidate_shortlist_recommendation() -> None:
    state = run_recruitment_workflow(PYTHON_REQUEST)
    shortlist = (state.get("analysis_results") or {}).get("shortlist_candidates") or []
    assert "C001" in shortlist
    assert state["decision"]["outcome"] == "pending_approval"
    assert state["status"] == "awaiting_human_approval"
    assert "recruitment_action" not in _agent_names(state)


def test_policy_violation_cannot_shortlist_c004() -> None:
    state = run_recruitment_workflow(J001_REQUEST)
    shortlist = (state.get("analysis_results") or {}).get("shortlist_candidates") or []
    assert "C004" not in shortlist
    validations = {
        item["candidate_id"]: item
        for item in (state.get("policy_results") or {}).get("candidate_validations") or []
    }
    assert validations["C004"]["eligible_for_shortlist"] is False
    assert validations["C004"]["violations"]


def test_human_approval_blocks_actions_until_resume() -> None:
    engine = get_workflow_engine()
    paused = engine.run(J001_REQUEST)
    assert paused.state["status"] == "awaiting_human_approval"
    assert paused.state["completed_actions"] == []
    assert paused.audit.approval_checkpoint is not None

    resumed = engine.resume(
        paused.state["workflow_id"],
        ApprovalDecision(approved=True, decided_by="recruiter-1", comment="Proceed"),
    )
    state = resumed.state
    assert state["decision"]["outcome"] == "approve"
    assert any(item.get("type") == "shortlist_candidate" for item in state["completed_actions"])
    assert any(item.get("type") == "schedule_interview" for item in state["completed_actions"])
    assert any(item.get("type") == "notify_candidate" for item in state["completed_actions"])
    assert any(item.get("type") == "notify_recruiter" for item in state["completed_actions"])


def test_interview_and_notification_only_after_approval() -> None:
    state = run_recruitment_workflow(PYTHON_REQUEST)
    assert "schedule_interview" not in _tool_names(state)
    assert "notify_candidate" not in _tool_names(state)


def test_tool_failure_path_for_job_lookup() -> None:
    reset_recruitment_store()
    get_recruitment_store().inject_error("get_job", times=3)
    state = create_initial_state(J001_REQUEST, workflow_type="recruitment")
    state["entities"] = {"job_id": "J001"}
    from app.agents.recruitment.job_research import job_research_agent

    patch = job_research_agent(state)
    assert patch.get("retrieved_data", {}).get("job_found") is False
    assert patch.get("errors")
    reset_recruitment_store()
    clean = run_recruitment_workflow(J001_REQUEST)
    assert (clean.get("retrieved_data") or {}).get("job", {}).get("job_id") == "J001"


def test_idempotent_shortlist_and_interview() -> None:
    store = reset_recruitment_store()
    first = store.shortlist_candidate(
        workflow_id="wf-1",
        job_id="J001",
        candidate_id="C001",
        score=99,
    )
    second = store.shortlist_candidate(
        workflow_id="wf-1",
        job_id="J001",
        candidate_id="C001",
        score=99,
    )
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True

    i1 = store.schedule_interview(
        workflow_id="wf-1",
        job_id="J001",
        candidate_id="C001",
    )
    i2 = store.schedule_interview(
        workflow_id="wf-1",
        job_id="J001",
        candidate_id="C001",
    )
    assert i1["idempotent_replay"] is False
    assert i2["idempotent_replay"] is True


def test_memory_and_knowledge_recorded() -> None:
    result = get_workflow_engine().run(PYTHON_REQUEST)
    accesses = result.state.get("memory_accesses") or []
    layers = {item.get("layer") for item in accesses}
    assert "short_term" in layers
    assert "knowledge" in layers
    assert any(item.get("layer") == "long_term" for item in accesses)


def test_organization_context_preserved() -> None:
    result = get_workflow_engine().run(
        PYTHON_REQUEST,
        organization_id="org-acme",
        user_id="recruiter-9",
        user_role="recruiter",
    )
    assert result.state["organization_id"] == "org-acme"
    assert result.state["user_id"] == "recruiter-9"
    assert result.audit.organization_id == "org-acme"
    assert result.metrics.organization_id == "org-acme"


def test_recruitment_tools_registered() -> None:
    registry = get_registry()
    for name in (
        "get_job",
        "search_jobs",
        "search_candidates",
        "get_candidate",
        "calculate_candidate_score",
        "validate_recruitment_policy",
        "shortlist_candidate",
        "schedule_interview",
        "notify_candidate",
        "notify_recruiter",
    ):
        assert registry.get(name)


def test_weak_and_borderline_paths() -> None:
    state = run_recruitment_workflow(J001_REQUEST)
    rejected = (state.get("analysis_results") or {}).get("rejected_candidates") or []
    review = (state.get("analysis_results") or {}).get("review_candidates") or []
    assert "C003" in rejected
    assert "C004" in review or "C002" in review or "C002" in rejected
