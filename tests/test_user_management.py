"""Admin user management, invitations, and organization isolation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.auth.security import hash_password, hash_invite_token
from app.auth.store import DEV_PASSWORD
from app.database.repositories.user import UserRepository
from app.database.session import session_scope

INVITE_PASSWORD = "invitePass-123"


def client() -> TestClient:
    return TestClient(app)


def _login(api: TestClient, username: str, password: str = DEV_PASSWORD):
    return api.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def _headers(api: TestClient, username: str, password: str = DEV_PASSWORD) -> dict[str, str]:
    response = _login(api, username, password)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_lists_organization_users() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.get("/api/v1/users", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    usernames = {item["username"] for item in body["users"]}
    assert "admin001" in usernames
    assert "employee001" in usernames
    assert "employee_other" not in usernames
    assert "password_hash" not in response.text
    assert "$2" not in response.text
    for item in body["users"]:
        assert item["organization_id"] == "demo-org"


def test_admin_can_invite_and_assign_operational_roles() -> None:
    api = client()
    headers = _headers(api, "admin001")
    cases = [
        ("test.employee@example.com", "employee", "Test Employee"),
        ("test.manager@example.com", "manager", "Test Manager"),
        ("test.hr@example.com", "hr", "Test HR"),
    ]
    for email, role, name in cases:
        invited = api.post(
            "/api/v1/users/invite",
            headers=headers,
            json={
                "full_name": name,
                "email": email,
                "role": role,
                "organization_id": "spoof-org",
                "user_role": "admin",
                **({"employee_id": "E002"} if role == "employee" else {}),
            },
        )
        assert invited.status_code == 200, invited.text
        payload = invited.json()
        assert payload["user"]["role"] == role
        if role == "employee":
            assert payload["user"]["employee_id"] == "E002"
        assert payload["user"]["status"] == "invited"
        assert payload["user"]["organization_id"] == "demo-org"
        assert payload["user"]["username"] == email
        assert payload["invitation"]["activation_token"]
        assert "password" not in payload["user"]
        login = _login(api, email, INVITE_PASSWORD)
        assert login.status_code == 401


def test_invite_rejects_admin_role() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Would Be Admin",
            "email": "would.be.admin@example.com",
            "role": "admin",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_employee_and_manager_cannot_manage_users() -> None:
    api = client()
    for username in ("employee001", "manager001", "hr001"):
        headers = _headers(api, username)
        listed = api.get("/api/v1/users", headers=headers)
        assert listed.status_code == 403
        assert listed.json()["error"]["code"] == "FORBIDDEN"
        invited = api.post(
            "/api/v1/users/invite",
            headers=headers,
            json={
                "full_name": "Nope",
                "email": f"{username}.invite@example.com",
                "role": "employee",
            },
        )
        assert invited.status_code == 403


def test_unauthenticated_user_management_is_401() -> None:
    api = client()
    assert api.get("/api/v1/users").status_code == 401
    assert api.post(
        "/api/v1/users/invite",
        json={"full_name": "X", "email": "x@example.com", "role": "employee"},
    ).status_code == 401


def test_cross_organization_access_blocked() -> None:
    api = client()
    headers = _headers(api, "admin001")
    listed = api.get("/api/v1/users", headers=headers)
    ids = {item["user_id"] for item in listed.json()["users"]}
    assert "user-employee-other" not in ids
    hidden = api.get("/api/v1/users/user-employee-other", headers=headers)
    assert hidden.status_code == 404
    patch = api.patch(
        "/api/v1/users/user-employee-other",
        headers=headers,
        json={"role": "manager"},
    )
    assert patch.status_code == 404


def test_admin_cannot_deactivate_self() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.post("/api/v1/users/user-admin-001/deactivate", headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SELF_ACTION_FORBIDDEN"
    assert _login(api, "admin001").status_code == 200


def test_last_admin_cannot_be_removed() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.patch(
        "/api/v1/users/user-admin-001",
        headers=headers,
        json={"role": "employee"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LAST_ADMIN"


def test_duplicate_invite_email_rejected() -> None:
    api = client()
    headers = _headers(api, "admin001")
    body = {
        "full_name": "Dup User",
        "email": "dup.user@example.com",
        "role": "employee",
        "employee_id": "E003",
    }
    first = api.post("/api/v1/users/invite", headers=headers, json=body)
    assert first.status_code == 200, first.text
    second = api.post("/api/v1/users/invite", headers=headers, json=body)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ACCOUNT_EXISTS"


def test_invitation_activation_and_login() -> None:
    api = client()
    headers = _headers(api, "admin001")
    invited = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Priya Nair",
            "email": "priya.nair@example.com",
            "role": "manager",
        },
    )
    assert invited.status_code == 200, invited.text
    token = invited.json()["invitation"]["activation_token"]
    user_id = invited.json()["user"]["user_id"]

    premature = _login(api, "priya.nair@example.com", INVITE_PASSWORD)
    assert premature.status_code == 401

    with session_scope() as session:
        record = UserRepository(session).get_by_user_id(user_id)
        assert record is not None
        assert record.invite_token_hash == hash_invite_token(token)
        assert record.password_hash
        assert INVITE_PASSWORD not in record.password_hash
        assert token not in record.invite_token_hash

    activated = api.post(
        "/api/v1/auth/activate",
        json={
            "token": token,
            "password": INVITE_PASSWORD,
            "confirm_password": INVITE_PASSWORD,
            "role": "admin",
            "organization_id": "spoof-org",
        },
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["user"]["role"] == "manager"
    assert activated.json()["user"]["status"] == "active"
    assert INVITE_PASSWORD not in activated.text

    reused = api.post(
        "/api/v1/auth/activate",
        json={
            "token": token,
            "password": INVITE_PASSWORD,
            "confirm_password": INVITE_PASSWORD,
        },
    )
    assert reused.status_code == 400

    login = _login(api, "priya.nair@example.com", INVITE_PASSWORD)
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "manager"


def test_deactivate_and_reactivate_blocks_login() -> None:
    api = client()
    headers = _headers(api, "admin001")
    deactivated = api.post("/api/v1/users/user-employee-001/deactivate", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"
    blocked = _login(api, "employee001")
    assert blocked.status_code == 401

    reactivated = api.post("/api/v1/users/user-employee-001/activate", headers=headers)
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"
    allowed = _login(api, "employee001")
    assert allowed.status_code == 200


def test_role_change_persists() -> None:
    api = client()
    headers = _headers(api, "admin001")
    changed = api.patch(
        "/api/v1/users/user-employee-001",
        headers=headers,
        json={"role": "manager", "organization_id": "other-org"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "manager"
    assert changed.json()["organization_id"] == "demo-org"
    detail = api.get("/api/v1/users/user-employee-001", headers=headers)
    assert detail.json()["role"] == "manager"
    login = _login(api, "employee001")
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "manager"


def test_cannot_admin_activate_invited_without_password() -> None:
    api = client()
    headers = _headers(api, "admin001")
    invited = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Pending User",
            "email": "pending.user@example.com",
            "role": "employee",
            "employee_id": "E004",
        },
    )
    user_id = invited.json()["user"]["user_id"]
    activate = api.post(f"/api/v1/users/{user_id}/activate", headers=headers)
    assert activate.status_code == 400


def test_existing_demo_users_still_login() -> None:
    api = client()
    for username, role in (
        ("employee001", "employee"),
        ("manager001", "manager"),
        ("hr001", "hr"),
        ("admin001", "admin"),
    ):
        response = _login(api, username)
        assert response.status_code == 200, response.text
        assert response.json()["user"]["role"] == role


def test_invite_token_hash_not_plaintext() -> None:
    api = client()
    headers = _headers(api, "admin001")
    invited = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Hash Check",
            "email": "hash.check@example.com",
            "role": "hr",
        },
    )
    token = invited.json()["invitation"]["activation_token"]
    listed = api.get("/api/v1/users", headers=headers)
    assert token not in listed.text
    assert hash_password("unused-check")
    detail = api.get(
        f"/api/v1/users/{invited.json()['user']['user_id']}",
        headers=headers,
    )
    assert "invite_token" not in detail.text
    assert "password_hash" not in detail.text


def test_admin_directory_lists_org_employees_and_bindings() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.get("/api/v1/employees", headers=headers)
    assert response.status_code == 200, response.text
    employees = {item["employee_id"]: item for item in response.json()["employees"]}
    assert "E001" in employees
    assert employees["E001"]["name"] == "Alex Rivera"
    assert employees["E001"]["available"] is False
    assert employees["E001"]["bound_user_id"] == "user-employee-001"
    assert "leave_balances" not in employees["E001"]
    assert employees["E002"]["available"] is True
    assert api.get("/api/v1/employees", headers=_headers(api, "employee001")).status_code == 403


def test_admin_can_bind_invited_employee_to_valid_record() -> None:
    api = client()
    headers = _headers(api, "admin001")
    invited = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Jordan Chen Account",
            "email": "jordan.bound@example.com",
            "role": "employee",
            "employee_id": "E002",
        },
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["user"]["employee_id"] == "E002"
    assert invited.json()["user"]["organization_id"] == "demo-org"


def test_invite_employee_without_binding_is_rejected() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "No Binding",
            "email": "no.binding@example.com",
            "role": "employee",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPLOYEE_BINDING_REQUIRED"


def test_duplicate_employee_binding_rejected() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Dup Binding",
            "email": "dup.binding@example.com",
            "role": "employee",
            "employee_id": "E001",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMPLOYEE_ALREADY_BOUND"


def test_cross_organization_employee_binding_rejected() -> None:
    api = client()
    registered = api.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Admin",
            "email": "other.admin.bind@example.com",
            "password": "securePass-123",
            "confirm_password": "securePass-123",
            "organization_name": "Bind Isolation Org",
        },
    )
    assert registered.status_code == 200, registered.text
    token = _login(api, "other.admin.bind@example.com", "securePass-123").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    directory = api.get("/api/v1/employees", headers=headers)
    assert directory.status_code == 200
    ids = {item["employee_id"] for item in directory.json()["employees"]}
    assert "E001" not in ids
    invited = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Spoof Employee",
            "email": "spoof.employee@example.com",
            "role": "employee",
            "employee_id": "E001",
        },
    )
    assert invited.status_code == 400
    assert invited.json()["error"]["code"] == "EMPLOYEE_NOT_FOUND"


def test_arbitrary_employee_id_rejected() -> None:
    api = client()
    headers = _headers(api, "admin001")
    response = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Fake Record",
            "email": "fake.record@example.com",
            "role": "employee",
            "employee_id": "E999",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPLOYEE_NOT_FOUND"


def test_admin_can_bind_existing_unbound_employee_via_patch() -> None:
    api = client()
    headers = _headers(api, "admin001")
    invited = api.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Later Bound",
            "email": "later.bound@example.com",
            "role": "hr",
        },
    )
    user_id = invited.json()["user"]["user_id"]
    patched = api.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"role": "employee", "employee_id": "E005"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["role"] == "employee"
    assert patched.json()["employee_id"] == "E005"
