"""Module 5C PostgreSQL persistence tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.api.main import app
from app.auth.security import hash_password, verify_password
from app.auth.store import DEV_PASSWORD
from app.config.settings import get_settings
from app.database.base import utc_now
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.persistence import PersistenceService
from app.database.repositories.organization import OrganizationRepository
from app.database.repositories.user import UserRepository
from app.database.repositories.workflow import WorkflowRepository
from app.database.session import get_engine, reset_engine, session_scope
from app.workflows.contracts import (
    ApprovalDecision,
    WorkflowAuditSnapshot,
    WorkflowResult,
    WorkflowRunMetrics,
)
from app.workflows.engine import get_workflow_engine, reset_workflow_engine


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _login(client: TestClient, username: str, password: str = DEV_PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = _login(client, username)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_database_connection() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_organization_creation() -> None:
    with session_scope() as session:
        org = OrganizationRepository(session).create(
            organization_id="org-create-test",
            name="Create Test Org",
        )
        assert org.organization_id == "org-create-test"
        assert org.is_active is True
        assert org.created_at is not None


def test_user_creation_and_lookup() -> None:
    with session_scope() as session:
        OrganizationRepository(session).create(
            organization_id="org-user-test",
            name="User Test Org",
        )
        hashed = hash_password("secret-value", rounds=4)
        UserRepository(session).create(
            user_id="u-lookup",
            organization_id="org-user-test",
            username="lookup_user",
            password_hash=hashed,
            role="employee",
            employee_id="E777",
        )
    with session_scope() as session:
        found = UserRepository(session).get_auth_user_by_username("lookup_user")
        assert found is not None
        assert found.user_id == "u-lookup"
        assert found.organization_id == "org-user-test"
        assert verify_password("secret-value", found.password_hash)
        assert found.password_hash != "secret-value"


def test_password_hash_persistence() -> None:
    with session_scope() as session:
        record = UserRepository(session).get_by_username("employee001")
        assert record is not None
        assert record.password_hash.startswith("$2")
        assert DEV_PASSWORD not in record.password_hash
        assert verify_password(DEV_PASSWORD, record.password_hash)


def test_login_using_database_user(client: TestClient) -> None:
    response = _login(client, "hr001")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "hr001"
    assert body["user"]["organization_id"] == "demo-org"
    assert "password_hash" not in body["user"]


def test_inactive_user_rejection(client: TestClient) -> None:
    response = _login(client, "inactive001")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_organization_isolation_users() -> None:
    with session_scope() as session:
        demo = UserRepository(session).get_auth_user_by_username("employee001")
        other = UserRepository(session).get_auth_user_by_username("employee_other")
    assert demo is not None and other is not None
    assert demo.organization_id == "demo-org"
    assert other.organization_id == "other-org"
    assert demo.organization_id != other.organization_id


def _sample_result(
    *,
    workflow_id: str,
    organization_id: str,
    user_id: str = "user-hr-001",
    status: str = "completed",
    employee_id: str = "E001",
) -> WorkflowResult:
    state = {
        "workflow_id": workflow_id,
        "organization_id": organization_id,
        "workflow_type": "leave_attendance",
        "user_id": user_id,
        "user_role": "hr",
        "status": status,
        "current_stage": "response",
        "created_at": utc_now().isoformat(),
        "final_response": "ok",
        "requires_human_approval": status == "awaiting_human_approval",
        "pending_actions": [{"type": "notify"}] if status == "awaiting_human_approval" else [],
        "completed_actions": [],
        "errors": [],
        "entities": {"employee_id": employee_id},
        "employee_data": {"employee_id": employee_id},
        "decision": {
            "outcome": "approve" if status == "completed" else "escalate",
            "rationale": "test",
            "confidence": 0.9,
            "executable": status == "completed",
            "requires_human_approval": status == "awaiting_human_approval",
            "entity_refs": {"employee_id": employee_id},
            "evidence": ["e1"],
            "blockers": [],
            "warnings": [],
            "influenced_by": [],
        },
        "confidence": 0.9,
        "metadata": {},
    }
    if status == "awaiting_human_approval":
        state["metadata"] = {
            "approval": {
                "status": "awaiting",
                "required_role": "manager",
                "reason": "needs review",
                "pending_actions": state["pending_actions"],
                "created_at": state["created_at"],
            }
        }
    return WorkflowResult(
        state=state,
        audit=WorkflowAuditSnapshot(
            workflow_id=workflow_id,
            organization_id=organization_id,
            workflow_type="leave_attendance",
            started_at=state["created_at"],
            completed_at=state["created_at"],
            status=status,
            final_outcome=str(state["decision"]["outcome"]),
            agents_executed=[{"agent": "decision"}],
            tool_executions=[{"tool_name": "t1", "success": True}],
            memory_accesses=[],
            decision=dict(state["decision"]),
            pending_actions=list(state["pending_actions"]),
            completed_actions=[],
            errors=[],
            approval_checkpoint=state["metadata"].get("approval"),
        ),
        metrics=WorkflowRunMetrics(
            duration_ms=12.5,
            agent_count=1,
            tool_count=1,
            tool_success_rate=1.0,
            retry_count=0,
            validation_failed=False,
            human_approval_required=status == "awaiting_human_approval",
            decision_confidence=0.9,
            action_success_rate=0.0,
            escalated=False,
            workflow_type="leave_attendance",
            organization_id=organization_id,
            status=status,
        ),
    )


def test_workflow_persistence_and_retrieval() -> None:
    result = _sample_result(workflow_id="wf-persist-1", organization_id="demo-org")
    with session_scope() as session:
        PersistenceService(session).persist_workflow_result(result)
    with session_scope() as session:
        loaded = PersistenceService(session).get_result(
            "wf-persist-1", organization_id="demo-org"
        )
    assert loaded is not None
    assert loaded.state["workflow_id"] == "wf-persist-1"
    assert loaded.audit.workflow_id == "wf-persist-1"
    assert loaded.metrics.duration_ms == 12.5


def test_workflow_listing() -> None:
    with session_scope() as session:
        svc = PersistenceService(session)
        svc.persist_workflow_result(
            _sample_result(workflow_id="wf-list-1", organization_id="demo-org")
        )
        svc.persist_workflow_result(
            _sample_result(workflow_id="wf-list-2", organization_id="demo-org")
        )
        items, total = svc.list_results(organization_id="demo-org", limit=10, offset=0)
    assert total >= 2
    ids = {item.state["workflow_id"] for item in items}
    assert "wf-list-1" in ids and "wf-list-2" in ids


def test_decision_audit_metrics_persistence() -> None:
    result = _sample_result(workflow_id="wf-dam-1", organization_id="demo-org")
    with session_scope() as session:
        PersistenceService(session).persist_workflow_result(result)
        run = WorkflowRepository(session).get_by_workflow_id(
            "wf-dam-1", organization_id="demo-org"
        )
        assert run is not None
        assert run.decision is not None
        assert run.decision.outcome == "approve"
        assert run.decision.evidence == ["e1"]
        assert run.audit is not None
        assert run.audit.agents_executed[0]["agent"] == "decision"
        assert run.metrics is not None
        assert run.metrics.agent_count == 1
        assert run.metrics.success is True


def test_pending_approval_persistence_and_resume_checkpoint() -> None:
    result = _sample_result(
        workflow_id="wf-appr-1",
        organization_id="demo-org",
        status="awaiting_human_approval",
    )
    with session_scope() as session:
        svc = PersistenceService(session)
        svc.persist_workflow_result(result)
        checkpoint = svc.load_approval_checkpoint(
            "wf-appr-1", organization_id="demo-org"
        )
        assert checkpoint is not None
        assert checkpoint["status"] == "awaiting_human_approval"
        approval = svc.approvals.get_by_workflow_id(
            "wf-appr-1", organization_id="demo-org"
        )
        assert approval is not None
        assert approval.decision == "awaiting"


def test_cross_organization_workflow_access_denied() -> None:
    result = _sample_result(workflow_id="wf-xorg-1", organization_id="demo-org")
    with session_scope() as session:
        PersistenceService(session).persist_workflow_result(result)
        missing = PersistenceService(session).get_result(
            "wf-xorg-1", organization_id="other-org"
        )
    assert missing is None


def test_api_cross_org_workflow_not_found(client: TestClient) -> None:
    hr = _headers(client, "hr001")
    created = client.post(
        "/api/v1/workflows/run",
        headers=hr,
        json={
            "request": "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        },
    )
    assert created.status_code == 200
    workflow_id = created.json()["workflow_id"]

    other = _headers(client, "hr_other")
    denied = client.get(f"/api/v1/workflows/{workflow_id}", headers=other)
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "WORKFLOW_NOT_FOUND"


def test_employee_ownership_via_api(client: TestClient) -> None:
    emp = _headers(client, "employee001")
    own = client.post(
        "/api/v1/workflows/run",
        headers=emp,
        json={
            "request": "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        },
    )
    assert own.status_code == 200
    workflow_id = own.json()["workflow_id"]
    assert client.get(f"/api/v1/workflows/{workflow_id}", headers=emp).status_code == 200

    listed = client.get("/api/v1/workflows", headers=emp)
    assert listed.status_code == 200
    assert any(item["workflow_id"] == workflow_id for item in listed.json()["workflows"])


def test_manager_hr_admin_access(client: TestClient) -> None:
    hr = _headers(client, "hr001")
    created = client.post(
        "/api/v1/workflows/run",
        headers=hr,
        json={
            "request": "Check whether employee E002 can take 3 days of leave from 2026-08-17."
        },
    )
    workflow_id = created.json()["workflow_id"]
    for username in ("manager001", "hr001", "admin001"):
        headers = _headers(client, username)
        assert client.get(f"/api/v1/workflows/{workflow_id}", headers=headers).status_code == 200


def test_timestamps_on_persisted_records() -> None:
    result = _sample_result(workflow_id="wf-ts-1", organization_id="demo-org")
    with session_scope() as session:
        run = PersistenceService(session).persist_workflow_result(result)
        assert run.created_at is not None
        assert run.updated_at is not None
        assert run.decision is not None
        assert run.decision.decided_at is not None


def test_transaction_rollback_on_failure() -> None:
    result = _sample_result(workflow_id="wf-rollback-1", organization_id="demo-org")
    with pytest.raises(Exception):
        with session_scope() as session:
            PersistenceService(session).persist_workflow_result(result)
            raise RuntimeError("force rollback")
    with session_scope() as session:
        assert (
            PersistenceService(session).get_result(
                "wf-rollback-1", organization_id="demo-org"
            )
            is None
        )


def test_database_unavailable_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_engine()
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://invalid:invalid@127.0.0.1:1/nope")
    get_settings.cache_clear()
    reset_engine()
    with pytest.raises(DatabaseUnavailableError):
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres@127.0.0.1:5433/enterprise_workflow_test",
    )
    get_settings.cache_clear()
    reset_engine()


def test_database_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # Empty string overrides .env so local developer DATABASE_URL cannot mask this case.
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    reset_engine()
    with pytest.raises(DatabaseNotConfiguredError):
        get_engine()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres@127.0.0.1:5433/enterprise_workflow_test",
    )
    get_settings.cache_clear()
    reset_engine()


def test_engine_persist_and_resume_from_database() -> None:
    reset_workflow_engine(with_persistence=True)
    engine = get_workflow_engine()
    pending = engine.run(
        "Check whether employee E001 can take 8 days of leave from 2026-08-17.",
        organization_id="demo-org",
        user_id="user-hr-001",
        user_role="hr",
    )
    workflow_id = str(pending.state["workflow_id"])
    assert pending.state["status"] == "awaiting_human_approval"

    # Simulate process restart: drop in-memory checkpoints.
    engine._checkpoints.clear()
    resumed = engine.resume(
        workflow_id,
        ApprovalDecision(approved=True, decided_by="user-manager-001", comment="ok"),
        organization_id="demo-org",
    )
    assert resumed.state["status"] == "completed"
    assert resumed.state["decision"]["outcome"] == "approve"

    with session_scope() as session:
        stored = PersistenceService(session).get_result(
            workflow_id, organization_id="demo-org"
        )
        approval = PersistenceService(session).approvals.get_by_workflow_id(
            workflow_id, organization_id="demo-org"
        )
    assert stored is not None
    assert stored.state["status"] == "completed"
    assert approval is not None
    assert approval.decision == "approved"
    reset_workflow_engine(with_persistence=False)


def test_api_persists_and_lists(client: TestClient) -> None:
    headers = _headers(client, "hr001")
    created = client.post(
        "/api/v1/workflows/run",
        headers=headers,
        json={
            "request": "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        },
    )
    assert created.status_code == 200
    workflow_id = created.json()["workflow_id"]
    listed = client.get("/api/v1/workflows", headers=headers)
    assert listed.status_code == 200
    assert any(item["workflow_id"] == workflow_id for item in listed.json()["workflows"])
    audit = client.get(f"/api/v1/workflows/{workflow_id}/audit", headers=headers)
    metrics = client.get(f"/api/v1/workflows/{workflow_id}/metrics", headers=headers)
    assert audit.status_code == 200
    assert metrics.status_code == 200
