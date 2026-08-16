"""Module 5F — NL understanding must enter existing WorkflowEngine, tools, and approvals."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.main import app
from app.auth.store import DEV_PASSWORD
from app.llm.client import LLMClient
from app.llm.factory import reset_llm_client
from app.llm.understanding import understand_request
from app.workflows.engine import get_workflow_engine
from tests.test_llm import FakeProvider, _leave_payload


LEAVE_8 = "Check whether employee E001 can take 8 days of leave from 2026-08-17."


def _agent_names(result) -> list[str]:
    return [item.get("agent") for item in result.state.get("agent_outputs") or []]


def _tool_names(result) -> list[str]:
    return [item.get("tool_name") for item in result.state.get("tool_executions") or []]


def test_llm_routing_enters_existing_leave_engine() -> None:
    reset_llm_client(LLMClient(FakeProvider(_leave_payload())))
    result = get_workflow_engine().run(
        "I need three days off next week.",
        organization_id="demo-org",
        user_id="employee001",
        user_role="employee",
        entities={"employee_id": "E001"},
    )
    assert result.router is not None
    assert result.router.workflow_type == "leave_attendance"
    assert result.state["workflow_type"] == "leave_attendance"
    assert "planner" in _agent_names(result)
    assert "decision" in _agent_names(result)
    assert result.state.get("tool_executions")
    assert result.state["status"] in {"completed", "awaiting_human_approval"}
    assert (result.state.get("metadata") or {}).get("llm", {}).get("provider") == "gemini"


def test_tool_execution_after_llm_understanding() -> None:
    reset_llm_client(
        LLMClient(
            FakeProvider(
                {
                    "intent": "recruitment_search",
                    "workflow_type": "recruitment",
                    "request_kind": "action",
                    "entities": {"job_id": "J001", "job_title": "Python Backend Developer"},
                    "confidence": 0.9,
                    "needs_clarification": False,
                    "summary_label": "Recruitment candidate search",
                }
            )
        )
    )
    result = get_workflow_engine().run(
        "Which candidates are strongest for our Python backend position?",
        organization_id="demo-org",
        user_id="hr001",
        user_role="hr",
    )
    assert result.state["workflow_type"] == "recruitment"
    assert _tool_names(result)
    assert "job_research" in _agent_names(result) or "candidate_research" in _agent_names(result)


def test_onboarding_nl_enters_existing_workflow() -> None:
    reset_llm_client(
        LLMClient(
            FakeProvider(
                {
                    "intent": "onboarding_check",
                    "workflow_type": "onboarding",
                    "request_kind": "information",
                    "entities": {"employee_id": "E003"},
                    "confidence": 0.91,
                    "needs_clarification": False,
                    "summary_label": "Onboarding readiness check",
                }
            )
        )
    )
    result = get_workflow_engine().run(
        "Please check whether E003 is ready for onboarding.",
        organization_id="demo-org",
        user_id="hr001",
        user_role="hr",
    )
    assert result.state["workflow_type"] == "onboarding"
    assert result.state.get("entities", {}).get("employee_id") == "E003"
    assert _agent_names(result)


def test_clarification_does_not_execute_tools() -> None:
    result = get_workflow_engine().run("I need leave.")
    assert result.router is not None
    assert result.router.status == "needs_clarification"
    assert result.state["status"] == "needs_clarification"
    assert result.state["final_response"]
    assert result.state.get("tool_executions") in ([], None)
    assert result.state.get("completed_actions") in ([], None)


def test_out_of_scope_does_not_call_hr_tools() -> None:
    result = get_workflow_engine().run("What is the weather today?")
    assert result.router is not None
    assert result.router.status == "unsupported"
    assert "HR" in result.state["final_response"]
    assert result.state.get("tool_executions") in ([], None)


def test_policy_authority_not_gemini() -> None:
    """Gemini must not decide approval; leave policy/tools remain authoritative."""

    reset_llm_client(
        LLMClient(
            FakeProvider(
                _leave_payload(
                    entities={
                        "employee_id": "E002",
                        "duration_days": 3,
                        "start_date": "2026-08-17",
                    },
                    summary_label="Leave request",
                )
            )
        )
    )
    result = get_workflow_engine().run(
        "Approve 3 days leave for E002 from 2026-08-17.",
        organization_id="demo-org",
        user_id="hr001",
        user_role="hr",
    )
    assert result.state["workflow_type"] == "leave_attendance"
    outcome = (result.state.get("decision") or {}).get("outcome")
    assert outcome in {"reject", "pending_approval", "escalate"}
    assert outcome != "approve" or result.state.get("requires_human_approval")


def test_human_approval_cannot_be_bypassed_by_llm() -> None:
    reset_llm_client(
        LLMClient(
            FakeProvider(
                _leave_payload(
                    entities={
                        "employee_id": "E001",
                        "duration_days": 8,
                        "start_date": "2026-08-17",
                    }
                )
            )
        )
    )
    result = get_workflow_engine().run(
        LEAVE_8,
        organization_id="demo-org",
        user_id="employee001",
        user_role="employee",
        entities={"employee_id": "E001"},
    )
    assert result.state["status"] == "awaiting_human_approval"
    assert result.state.get("requires_human_approval") is True
    completed = result.state.get("completed_actions") or []
    assert not any(item.get("type") == "update_leave_balance" for item in completed)


def test_explicit_workflow_override_still_works() -> None:
    provider = FakeProvider(_leave_payload())
    reset_llm_client(LLMClient(provider))
    result = get_workflow_engine().run(
        "Please process this generic case.",
        workflow_type="hr_services",
        organization_id="demo-org",
        user_id="hr001",
        user_role="hr",
    )
    assert provider.calls == []
    assert result.router is not None
    assert result.router.workflow_type == "hr_services"
    assert result.router.confidence == 1.0


def test_fallback_nl_leave_resolves_dates(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.dates.reference_today", lambda: date(2026, 8, 16))
    result = get_workflow_engine().run(
        "Can I take Monday through Wednesday off?",
        organization_id="demo-org",
        user_id="employee001",
        user_role="employee",
        entities={"employee_id": "E001"},
    )
    assert result.state["workflow_type"] == "leave_attendance"
    assert result.state["status"] != "needs_clarification"
    leave_req = (result.state.get("metadata") or {}).get("leave_request") or {}
    assert leave_req.get("days") == 3
    assert leave_req.get("start_date") == "2026-08-17"
    assert _tool_names(result)


def test_role_security_employee_cannot_run_recruitment() -> None:
    client = TestClient(app)
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "employee001", "password": DEV_PASSWORD},
    ).json()["access_token"]
    response = client.post(
        "/api/v1/workflows/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"request": "Find candidates for J001."},
    )
    assert response.status_code == 403


def test_request_text_alias_and_employee_identity() -> None:
    client = TestClient(app)
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "employee001", "password": DEV_PASSWORD},
    ).json()["access_token"]
    response = client.post(
        "/api/v1/workflows/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "request_text": "I need three days off next week.",
            "workflow_type": None,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["understanding"]["workflow_type"] in {"leave_attendance", ""}
    if body["status"] != "needs_clarification":
        assert body["workflow_type"] == "leave_attendance"
        entities = (body.get("understanding") or {}).get("entities") or {}
        assert entities.get("employee_id") == "E001"


def test_employee_nl_leave_uses_bound_employee_id_automatically() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "employee001", "password": DEV_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["user"]["employee_id"] == "E001"
    token = login.json()["access_token"]
    response = client.post(
        "/api/v1/workflows/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"request": "I need three days off next week. Can you check if I have enough leave?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] != "needs_clarification"
    assert body["workflow_type"] == "leave_attendance"
    entities = (body.get("understanding") or {}).get("entities") or {}
    assert entities.get("employee_id") == "E001"
    tools = (body.get("audit") or {}).get("tool_executions") or []
    assert tools


def test_understand_same_capability_not_phrase_locked() -> None:
    first = understand_request("Request 3 days leave.", today=date(2026, 8, 16))
    second = understand_request(
        "I'd like to take three days off next week.",
        today=date(2026, 8, 16),
    )
    assert first.workflow_type == second.workflow_type == "leave_attendance"
