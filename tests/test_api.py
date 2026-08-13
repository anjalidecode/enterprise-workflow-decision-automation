"""Module 5A FastAPI layer tests (TestClient; no live server required)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app, create_app
from app.config.settings import get_settings

ROOT = Path(__file__).resolve().parents[1]

ORG = "demo-org"
OTHER_ORG = "other-org"
USER = "demo-user"

RUN_CASES = [
    (
        "leave_attendance",
        "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
    ),
    (
        "recruitment",
        "Find candidates for the Python Backend Developer position.",
    ),
    ("onboarding", "Start onboarding for employee E003."),
    (
        "attendance",
        "Analyze attendance for employee E003 for July 2026.",
    ),
    (
        "performance",
        "Analyze performance for employee E003 for Q2 2026.",
    ),
    ("training", "Recommend training for employee E003."),
    ("offboarding", "Start offboarding for employee E006."),
    (
        "hr_services",
        "Request an employment certificate for employee E003.",
    ),
]

LEAVE_PENDING = "Check whether employee E001 can take 8 days of leave from 2026-08-17."


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _run_payload(
    request: str,
    *,
    organization_id: str = ORG,
    workflow_type: str | None = None,
    user_id: str = USER,
    user_role: str = "hr",
) -> dict:
    body: dict = {
        "request": request,
        "organization_id": organization_id,
        "user_id": user_id,
        "user_role": user_role,
    }
    if workflow_type is not None:
        body["workflow_type"] = workflow_type
    return body


def test_application_starts() -> None:
    application = create_app()
    assert application.title
    assert application.version
    with TestClient(application) as local:
        response = local.get("/api/v1/health")
        assert response.status_code == 200


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "enterprise-workflow-decision-automation"
    assert body["version"]
    assert body["environment"]
    assert "X-Request-ID" in response.headers


def test_workflow_types_from_registry(client: TestClient) -> None:
    response = client.get("/api/v1/workflows/types")
    assert response.status_code == 200
    types = {item["workflow_type"] for item in response.json()["workflows"]}
    expected = {case[0] for case in RUN_CASES}
    assert expected.issubset(types)
    for item in response.json()["workflows"]:
        assert item["name"]
        assert item["description"]


@pytest.mark.parametrize("workflow_type,request_text", RUN_CASES)
def test_run_each_workflow_type(
    client: TestClient, workflow_type: str, request_text: str
) -> None:
    response = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(request_text, workflow_type=workflow_type),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"]
    assert body["workflow_type"] == workflow_type
    assert body["status"]
    assert body["organization_id"] == ORG
    assert "decision" in body
    assert "response" in body
    assert body["audit"] is not None
    assert body["metrics"] is not None


def test_explicit_workflow_type(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(
            "Please process this case for employee E003.",
            workflow_type="hr_services",
        ),
    )
    assert response.status_code == 200
    assert response.json()["workflow_type"] == "hr_services"


def test_automatic_routing(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(
            "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        ),
    )
    assert response.status_code == 200
    assert response.json()["workflow_type"] == "leave_attendance"


def test_invalid_request_empty_body(client: TestClient) -> None:
    response = client.post("/api/v1/workflows/run", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["request_id"]


def test_invalid_request_blank_text(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workflows/run",
        json=_run_payload("   "),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_workflow_not_found(client: TestClient) -> None:
    response = client.get(
        "/api/v1/workflows/missing-id",
        params={"organization_id": ORG},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "WORKFLOW_NOT_FOUND"
    assert "stack" not in body["error"]["message"].lower()
    assert "Traceback" not in body["error"]["message"]


def test_organization_isolation(client: TestClient) -> None:
    created = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(
            "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
            organization_id=ORG,
        ),
    )
    assert created.status_code == 200
    workflow_id = created.json()["workflow_id"]

    denied = client.get(
        f"/api/v1/workflows/{workflow_id}",
        params={"organization_id": OTHER_ORG},
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "WORKFLOW_NOT_FOUND"

    allowed = client.get(
        f"/api/v1/workflows/{workflow_id}",
        params={"organization_id": ORG},
    )
    assert allowed.status_code == 200
    assert allowed.json()["workflow_id"] == workflow_id

    listed_other = client.get(
        "/api/v1/workflows",
        params={"organization_id": OTHER_ORG},
    )
    assert listed_other.status_code == 200
    assert listed_other.json()["total"] == 0

    listed = client.get(
        "/api/v1/workflows",
        params={"organization_id": ORG},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert all(item["organization_id"] == ORG for item in listed.json()["workflows"])


def test_get_list_audit_metrics(client: TestClient) -> None:
    created = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(
            "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        ),
    )
    workflow_id = created.json()["workflow_id"]

    got = client.get(
        f"/api/v1/workflows/{workflow_id}",
        params={"organization_id": ORG},
    )
    assert got.status_code == 200
    assert got.json()["workflow_id"] == workflow_id
    assert got.json()["audit"]["workflow_id"] == workflow_id

    listed = client.get(
        "/api/v1/workflows",
        params={
            "organization_id": ORG,
            "workflow_type": "leave_attendance",
            "limit": 10,
            "offset": 0,
        },
    )
    assert listed.status_code == 200
    assert "in-memory" in listed.json()["note"].lower()
    assert any(item["workflow_id"] == workflow_id for item in listed.json()["workflows"])

    audit = client.get(
        f"/api/v1/workflows/{workflow_id}/audit",
        params={"organization_id": ORG},
    )
    assert audit.status_code == 200
    assert audit.json()["workflow_id"] == workflow_id
    assert "agents" in audit.json()
    assert "tool_executions" in audit.json()

    metrics = client.get(
        f"/api/v1/workflows/{workflow_id}/metrics",
        params={"organization_id": ORG},
    )
    assert metrics.status_code == 200
    assert "duration_ms" in metrics.json()
    assert "agent_count" in metrics.json()
    assert "success" in metrics.json()


def test_pending_approve_reject_and_invalid_resume(client: TestClient) -> None:
    pending = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(LEAVE_PENDING),
    )
    assert pending.status_code == 200
    body = pending.json()
    assert body["status"] == "awaiting_human_approval"
    assert body["approval_status"] == "awaiting"
    workflow_id = body["workflow_id"]

    approved = client.post(
        f"/api/v1/workflows/{workflow_id}/approve",
        params={"organization_id": ORG},
        json={
            "user_id": "manager-001",
            "user_role": "manager",
            "reason": "Approved after review.",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "completed"
    assert approved.json()["decision"]["outcome"] == "approve"

    # Second resume should conflict.
    again = client.post(
        f"/api/v1/workflows/{workflow_id}/approve",
        params={"organization_id": ORG},
        json={"user_id": "manager-001", "reason": "duplicate"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "WORKFLOW_NOT_RESUMABLE"

    # Reject path on a fresh pending run.
    pending2 = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(LEAVE_PENDING),
    )
    wid2 = pending2.json()["workflow_id"]
    rejected = client.post(
        f"/api/v1/workflows/{wid2}/reject",
        params={"organization_id": ORG},
        json={
            "user_id": "manager-001",
            "user_role": "manager",
            "reason": "Rejected after review.",
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "completed"
    assert rejected.json()["decision"]["outcome"] == "reject"

    # Cross-org approve denied.
    pending3 = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(LEAVE_PENDING),
    )
    wid3 = pending3.json()["workflow_id"]
    cross = client.post(
        f"/api/v1/workflows/{wid3}/approve",
        params={"organization_id": OTHER_ORG},
        json={"user_id": "manager-001", "reason": "nope"},
    )
    assert cross.status_code == 404

    missing = client.post(
        "/api/v1/workflows/does-not-exist/approve",
        params={"organization_id": ORG},
        json={"user_id": "manager-001", "reason": "nope"},
    )
    assert missing.status_code == 404


def test_request_id_preserved_and_generated(client: TestClient) -> None:
    custom = "client-req-123"
    response = client.get(
        "/api/v1/health",
        headers={"X-Request-ID": custom},
    )
    assert response.headers["X-Request-ID"] == custom

    generated = client.get("/api/v1/health")
    assert generated.headers["X-Request-ID"]
    assert generated.headers["X-Request-ID"] != custom

    run = client.post(
        "/api/v1/workflows/run",
        headers={"X-Request-ID": "run-corr-1"},
        json=_run_payload(
            "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        ),
    )
    assert run.headers["X-Request-ID"] == "run-corr-1"
    assert run.json()["request_id"] == "run-corr-1"


def test_cors_configuration(client: TestClient) -> None:
    settings = get_settings()
    assert "*" not in settings.cors_origin_list
    assert any("localhost" in origin for origin in settings.cors_origin_list)

    origin = settings.cors_origin_list[0]
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == origin

    blocked = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert blocked.headers.get("access-control-allow-origin") != "https://evil.example"


def test_structured_error_and_response_schema(client: TestClient) -> None:
    response = client.get(
        "/api/v1/workflows/missing",
        params={"organization_id": ORG},
    )
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) >= {"code", "message", "request_id"}

    ok = client.post(
        "/api/v1/workflows/run",
        json=_run_payload(
            "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        ),
    )
    payload = ok.json()
    for key in (
        "workflow_id",
        "workflow_type",
        "status",
        "current_stage",
        "decision",
        "response",
        "audit",
        "metrics",
    ):
        assert key in payload


def test_openapi_docs_available(client: TestClient) -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200
    redoc = client.get("/redoc")
    assert redoc.status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/workflows/run" in paths


def test_cli_regression() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run.py"),
            "Check whether employee E001 can take 3 days of leave from 2026-08-17.",
            "--organization-id",
            ORG,
            "--user-id",
            USER,
            "--user-role",
            "hr",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "leave_attendance" in completed.stdout
    assert "Workflow ID:" in completed.stdout
