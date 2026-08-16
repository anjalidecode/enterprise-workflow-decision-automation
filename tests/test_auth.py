"""Module 5B authentication and RBAC tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.auth.security import hash_password
from app.auth.store import DEV_PASSWORD
from app.config.settings import get_settings
from app.database.persistence import PersistenceService
from app.database.repositories.user import UserRepository
from app.database.session import session_scope

LEAVE_OWN = "Check whether employee E001 can take 3 days of leave from 2026-08-17."
LEAVE_OTHER = "Check whether employee E002 can take 3 days of leave from 2026-08-17."
LEAVE_PENDING = "Check whether employee E001 can take 8 days of leave from 2026-08-17."


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


@pytest.mark.parametrize(
    "username,role",
    [
        ("employee001", "employee"),
        ("manager001", "manager"),
        ("hr001", "hr"),
        ("admin001", "admin"),
    ],
)
def test_successful_login_roles(client: TestClient, username: str, role: str) -> None:
    response = _login(client, username)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0
    assert body["user"]["role"] == role
    assert body["user"]["username"] == username
    assert "password" not in body
    assert "password_hash" not in body
    assert "password_hash" not in body["user"]
    dumped = response.text.lower()
    assert "password" not in dumped or "password" not in body["user"]
    assert DEV_PASSWORD not in response.text
    assert "jwt_secret" not in dumped
    assert get_settings().resolved_jwt_secret not in response.text


def test_invalid_username(client: TestClient) -> None:
    response = _login(client, "no-such-user")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_invalid_password(client: TestClient) -> None:
    response = _login(client, "employee001", password="wrong-password")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert "wrong-password" not in response.text


def test_inactive_user(client: TestClient) -> None:
    response = _login(client, "inactive001")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_missing_authorization_header(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_malformed_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_expired_token(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-employee-001",
            "organization_id": "demo-org",
            "role": "employee",
            "employee_id": "E001",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        get_settings().resolved_jwt_secret,
        algorithm=get_settings().jwt_algorithm,
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_invalid_signature(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-employee-001",
            "organization_id": "demo-org",
            "role": "employee",
            "employee_id": "E001",
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        "wrong-secret-key",
        algorithm="HS256",
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_auth_me(client: TestClient) -> None:
    headers = _headers(client, "employee001")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "employee001"
    assert body["role"] == "employee"
    assert body["employee_id"] == "E001"
    assert body["organization_id"] == "demo-org"
    assert "password_hash" not in body


def test_employee001_bound_to_e001(client: TestClient) -> None:
    with session_scope() as session:
        user = UserRepository(session).get_auth_user_by_username("employee001")
    assert user is not None
    assert user.role.value == "employee"
    assert user.organization_id == "demo-org"
    assert user.employee_id == "E001"


def test_employee_login_jwt_contains_employee_id(client: TestClient) -> None:
    response = _login(client, "employee001")
    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(
        token,
        get_settings().resolved_jwt_secret,
        algorithms=[get_settings().jwt_algorithm],
    )
    assert payload["sub"] == "user-employee-001"
    assert payload["organization_id"] == "demo-org"
    assert payload["role"] == "employee"
    assert payload["employee_id"] == "E001"
    assert "password" not in payload
    assert "password_hash" not in payload
    assert response.json()["user"]["employee_id"] == "E001"


def test_employee_cannot_override_employee_id_in_request_body(client: TestClient) -> None:
    headers = _headers(client, "employee001")
    ignored = client.post(
        "/api/v1/workflows/run",
        headers=headers,
        json={
            "request": "I need three days off next week. Can you check if I have enough leave?",
            "employee_id": "E002",
        },
    )
    assert ignored.status_code == 200, ignored.text
    entities = (ignored.json().get("understanding") or {}).get("entities") or {}
    assert entities.get("employee_id") == "E001"

    blocked = client.post(
        "/api/v1/workflows/run",
        headers=headers,
        json={"request": LEAVE_OTHER, "employee_id": "E002"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "FORBIDDEN"


def test_employee_cannot_bind_themselves_to_another_employee(client: TestClient) -> None:
    headers = _headers(client, "employee001")
    response = client.patch(
        "/api/v1/users/user-employee-001",
        headers=headers,
        json={"employee_id": "E002"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["employee_id"] == "E001"


def test_employee_own_data_and_blocked_other(client: TestClient) -> None:
    headers = _headers(client, "employee001")
    own = client.post(
        "/api/v1/workflows/run",
        headers=headers,
        json={"request": LEAVE_OWN},
    )
    assert own.status_code == 200
    assert own.json()["organization_id"] == "demo-org"
    assert own.json()["workflow_type"] == "leave_attendance"

    blocked = client.post(
        "/api/v1/workflows/run",
        headers=headers,
        json={"request": LEAVE_OTHER},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "FORBIDDEN"


def test_employee_blocked_from_admin_and_approval(client: TestClient) -> None:
    emp = _headers(client, "employee001")
    hr = _headers(client, "hr001")

    pending = client.post(
        "/api/v1/workflows/run",
        headers=hr,
        json={"request": LEAVE_PENDING},
    )
    assert pending.status_code == 200
    workflow_id = pending.json()["workflow_id"]

    approve = client.post(
        f"/api/v1/workflows/{workflow_id}/approve",
        headers=emp,
        json={"reason": "trying to approve", "user_role": "manager"},
    )
    assert approve.status_code == 403
    assert approve.json()["error"]["code"] == "FORBIDDEN"

    recruit = client.post(
        "/api/v1/workflows/run",
        headers=emp,
        json={
            "request": "Find candidates for the Python Backend Developer position.",
            "workflow_type": "recruitment",
        },
    )
    assert recruit.status_code == 403


def test_manager_hr_admin_permissions(client: TestClient) -> None:
    manager = _headers(client, "manager001")
    hr = _headers(client, "hr001")
    admin = _headers(client, "admin001")

    for headers in (manager, hr, admin):
        response = client.post(
            "/api/v1/workflows/run",
            headers=headers,
            json={"request": LEAVE_OTHER},
        )
        assert response.status_code == 200
        assert response.json()["organization_id"] == "demo-org"


def test_body_cannot_override_identity(client: TestClient) -> None:
    headers = _headers(client, "employee001")
    response = client.post(
        "/api/v1/workflows/run",
        headers=headers,
        json={
            "request": LEAVE_OWN,
            "organization_id": "other-org",
            "user_id": "user-admin-001",
            "user_role": "admin",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == "demo-org"
    # Authenticated employee identity is used, not spoofed admin.
    assert body["audit"]["organization_id"] == "demo-org"


def test_workflow_uses_authenticated_user(client: TestClient) -> None:
    headers = _headers(client, "hr001")
    response = client.post(
        "/api/v1/workflows/run",
        headers=headers,
        json={"request": LEAVE_OWN},
    )
    assert response.status_code == 200
    workflow_id = response.json()["workflow_id"]
    detail = client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
    assert detail.status_code == 200
    with session_scope() as session:
        indexed = PersistenceService(session).get_result(
            workflow_id, organization_id="demo-org"
        )
    assert indexed is not None
    assert indexed.state["user_id"] == "user-hr-001"
    assert indexed.state["user_role"] == "hr"
    assert indexed.state["organization_id"] == "demo-org"


def test_approval_requires_auth_and_authorized_roles(client: TestClient) -> None:
    hr = _headers(client, "hr001")
    manager = _headers(client, "manager001")
    pending = client.post(
        "/api/v1/workflows/run",
        headers=hr,
        json={"request": LEAVE_PENDING},
    )
    workflow_id = pending.json()["workflow_id"]

    unauth = client.post(
        f"/api/v1/workflows/{workflow_id}/approve",
        json={"reason": "no token"},
    )
    assert unauth.status_code == 401

    approved = client.post(
        f"/api/v1/workflows/{workflow_id}/approve",
        headers=manager,
        json={"reason": "OK", "user_id": "spoof", "user_role": "admin"},
    )
    assert approved.status_code == 200
    assert approved.json()["decision"]["outcome"] == "approve"

    with session_scope() as session:
        indexed = PersistenceService(session).get_result(
            workflow_id, organization_id="demo-org"
        )
    assert indexed is not None
    approval = (indexed.state.get("metadata") or {}).get("approval") or {}
    assert approval.get("decided_by") == "user-manager-001"


def test_rejection_authorization(client: TestClient) -> None:
    hr = _headers(client, "hr001")
    manager = _headers(client, "manager001")
    pending = client.post(
        "/api/v1/workflows/run",
        headers=hr,
        json={"request": LEAVE_PENDING},
    )
    workflow_id = pending.json()["workflow_id"]
    rejected = client.post(
        f"/api/v1/workflows/{workflow_id}/reject",
        headers=manager,
        json={"reason": "No"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["decision"]["outcome"] == "reject"


def test_employee_cannot_view_others_run(client: TestClient) -> None:
    hr = _headers(client, "hr001")
    emp = _headers(client, "employee001")
    created = client.post(
        "/api/v1/workflows/run",
        headers=hr,
        json={"request": LEAVE_OTHER},
    )
    workflow_id = created.json()["workflow_id"]
    denied = client.get(f"/api/v1/workflows/{workflow_id}", headers=emp)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN"

    audit = client.get(f"/api/v1/workflows/{workflow_id}/audit", headers=emp)
    assert audit.status_code == 403
    metrics = client.get(f"/api/v1/workflows/{workflow_id}/metrics", headers=emp)
    assert metrics.status_code == 403


def test_health_remains_public(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_openapi_bearer_security(client: TestClient) -> None:
    openapi = client.get("/openapi.json").json()
    assert openapi["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    assert openapi["security"] == [{"BearerAuth": []}]
    login = openapi["paths"]["/api/v1/auth/login"]["post"]
    assert login.get("security") == []
    register = openapi["paths"]["/api/v1/auth/register"]["post"]
    assert register.get("security") == []
    activate = openapi["paths"]["/api/v1/auth/activate"]["post"]
    assert activate.get("security") == []


def test_password_hashes_never_returned(client: TestClient) -> None:
    response = _login(client, "hr001")
    text = response.text
    with session_scope() as session:
        store_user = UserRepository(session).get_auth_user_by_username("hr001")
    assert store_user is not None
    assert store_user.password_hash
    assert store_user.password_hash not in text
    assert hash_password("probe")  # hashing still works
    assert "$2" not in text  # bcrypt markers should not appear in login response


def test_protected_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/workflows/types").status_code == 401
    assert client.get("/api/v1/workflows").status_code == 401
    assert (
        client.post(
            "/api/v1/workflows/run",
            json={"request": LEAVE_OWN},
        ).status_code
        == 401
    )


def _register_payload(**overrides: object) -> dict:
    body: dict = {
        "full_name": "Alex Rivera",
        "email": "alex.rivera@northwind.test",
        "password": "securePass-123",
        "confirm_password": "securePass-123",
        "organization_name": "Northwind HR",
        "role": "admin",
        "organization_id": "spoof-org",
        "employee_id": "E999",
        "user_role": "hr",
    }
    body.update(overrides)
    return body


def test_register_first_org_user_becomes_admin(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=_register_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"].startswith("Account created successfully.")
    assert body["notification"]["event_type"] == "USER_REGISTERED"
    assert body["notification"]["status"] in {"generated", "sent"}
    assert "password" not in body["message"].lower()
    assert body["user"]["username"] == "alex.rivera@northwind.test"
    assert body["user"]["role"] == "admin"
    assert body["user"]["organization_id"] == "northwind-hr"
    assert body["user"]["employee_id"] is None
    assert "password" not in body
    assert "password_hash" not in body["user"]
    assert "securePass-123" not in response.text
    assert "$2" not in response.text

    login = _login(client, "alex.rivera@northwind.test", password="securePass-123")
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["organization_id"] == "northwind-hr"

    with session_scope() as session:
        stored = UserRepository(session).get_auth_user_by_username(
            "alex.rivera@northwind.test"
        )
    assert stored is not None
    assert stored.role.value == "admin"
    assert stored.password_hash != "securePass-123"


def test_register_existing_organization_is_employee(client: TestClient) -> None:
    first = client.post("/api/v1/auth/register", json=_register_payload())
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/auth/register",
        json=_register_payload(
            full_name="Sam Lee",
            email="sam.lee@northwind.test",
            role="admin",
        ),
    )
    assert second.status_code == 200, second.text
    assert second.json()["user"]["role"] == "employee"
    assert second.json()["user"]["organization_id"] == "northwind-hr"


def test_register_duplicate_email(client: TestClient) -> None:
    assert client.post("/api/v1/auth/register", json=_register_payload()).status_code == 200
    again = client.post("/api/v1/auth/register", json=_register_payload())
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ACCOUNT_EXISTS"


def test_register_password_mismatch(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json=_register_payload(confirm_password="different-pass-1"),
    )
    assert response.status_code == 400
    assert "match" in response.json()["error"]["message"].lower()


def test_register_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json=_register_payload(email="not-an-email"),
    )
    assert response.status_code == 400


def test_register_weak_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json=_register_payload(password="short", confirm_password="short"),
    )
    assert response.status_code == 400
