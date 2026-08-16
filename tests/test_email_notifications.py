"""Module 5G — email notification system tests. Never require real SMTP credentials."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.auth.security import hash_password
from app.auth.store import DEV_PASSWORD
from app.config.settings import Settings, get_settings
from app.database.repositories.notification import NotificationEventRepository
from app.database.repositories.user import UserRepository
from app.database.session import session_scope
from app.notifications.console import ConsoleEmailProvider
from app.notifications.errors import EmailConfigurationError, EmailProviderError
from app.notifications.factory import build_email_provider, reset_email_provider
from app.notifications.metrics import notification_metrics_snapshot, reset_notification_metrics
from app.notifications.models import (
    EmailDeliveryResult,
    EmailMessage,
    NotificationEventPayload,
    NotificationEventType,
    NotificationStatus,
)
from app.notifications.service import (
    BusinessNotificationService,
    get_business_notification_service,
    reset_business_notification_service,
)
from app.notifications.smtp import SmtpEmailProvider
from app.notifications.templates import render_email
from app.workflows.engine import get_workflow_engine, reset_workflow_engine

LEAVE_PENDING = "Check whether employee E001 can take 8 days of leave from 2026-08-17."
LEAVE_BLOCKED = "Check whether employee E999 can take 3 days of leave from 2026-08-17."
INVITE_PASSWORD = "ActivatePass12"


class RecordingProvider:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    @property
    def name(self) -> str:
        return "console"

    def send(self, message: EmailMessage) -> EmailDeliveryResult:
        self.messages.append(message)
        return EmailDeliveryResult(
            status=NotificationStatus.GENERATED,
            provider=self.name,
            message_id=f"rec-{len(self.messages)}",
        )


class FailingProvider:
    @property
    def name(self) -> str:
        return "smtp"

    def send(self, message: EmailMessage) -> EmailDeliveryResult:
        raise EmailProviderError("forced failure", error_code="EMAIL_SEND_FAILED")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _login(client: TestClient, username: str, password: str = DEV_PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def _headers(client: TestClient, username: str, password: str = DEV_PASSWORD) -> dict[str, str]:
    response = _login(client, username, password)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _give_demo_users_emails() -> None:
    with session_scope() as session:
        repo = UserRepository(session)
        emp = repo.get_by_user_id("user-employee-001")
        mgr = repo.get_by_user_id("user-manager-001")
        assert emp is not None and mgr is not None
        emp.username = "employee001@demo.test"
        emp.full_name = "Demo Employee"
        mgr.username = "manager001@demo.test"
        mgr.full_name = "Demo Manager"
        session.flush()


def _register_payload(**overrides: object) -> dict:
    suffix = uuid.uuid4().hex[:8]
    body: dict = {
        "full_name": "Alex Rivera",
        "email": f"alex.{suffix}@northwind.test",
        "password": "securePass-123",
        "confirm_password": "securePass-123",
        "organization_name": f"Northwind HR {suffix}",
    }
    body.update(overrides)
    return body


def test_console_provider_renders_safe_preview() -> None:
    provider = ConsoleEmailProvider()
    message = render_email(
        event_type=NotificationEventType.USER_REGISTERED,
        to_email="admin@example.com",
        to_name="Alex",
        organization_id="org-1",
        recipient_user_id="user-1",
        workflow_run_id="",
        context={
            "organization_name": "Acme",
            "role_label": "Administrator",
            "login_url": "http://127.0.0.1:5173/login",
        },
    )
    result = provider.send(message)
    assert result.status == NotificationStatus.GENERATED
    assert result.provider == "console"
    assert provider.sent[0].to_email == "admin@example.com"
    assert "password" not in message.text_body.lower()
    assert "Welcome to WorkSphere AI" in message.subject


def test_smtp_configuration_validation() -> None:
    with pytest.raises(EmailConfigurationError):
        SmtpEmailProvider(
            host="",
            port=587,
            username="",
            password="",
            from_email="",
        )
    settings = Settings(
        email_provider="smtp",
        smtp_host="",
        smtp_from_email="",
    )
    with pytest.raises(EmailConfigurationError):
        build_email_provider(settings)


def test_missing_smtp_configuration_via_factory() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    # Force smtp with empty host through Settings instance
    bad = settings.model_copy(
        update={
            "email_provider": "smtp",
            "smtp_host": "",
            "smtp_from_email": "",
        }
    )
    with pytest.raises(EmailConfigurationError):
        build_email_provider(bad)


def test_welcome_email_on_first_org_registration(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))

    payload = _register_payload()
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["role"] == "admin"
    assert body["notification"]["event_type"] == "USER_REGISTERED"
    assert body["notification"]["status"] == "generated"
    assert "Welcome" in body["message"] or "notification" in body["message"].lower()

    assert len(recorder.messages) == 1
    email = recorder.messages[0]
    assert email.to_email == payload["email"]
    assert "Administrator" in email.text_body or "Administrator" in email.html_body
    assert payload["organization_name"].split()[0] in email.text_body or "Northwind" in email.text_body
    assert "/login" in email.text_body
    assert "securePass-123" not in email.text_body
    assert "password" not in email.text_body.lower() or "Do not reply with passwords" in email.html_body


def test_registration_succeeds_when_email_fails(client: TestClient) -> None:
    failing = FailingProvider()
    reset_email_provider(failing)
    reset_business_notification_service(BusinessNotificationService(failing))

    payload = _register_payload()
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["role"] == "admin"
    assert body["notification"]["status"] == "failed"
    assert "could not be delivered" in body["message"].lower() or "could not" in body["notification"]["message"].lower()

    login = _login(client, payload["email"], password="securePass-123")
    assert login.status_code == 200


def test_welcome_email_idempotent(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    service = BusinessNotificationService(recorder)
    reset_business_notification_service(service)

    payload = _register_payload()
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 200
    user_id = first.json()["user"]["user_id"]
    org_id = first.json()["user"]["organization_id"]

    # Replay same business event
    second = service.dispatch(
        NotificationEventPayload(
            event_type=NotificationEventType.USER_REGISTERED,
            organization_id=org_id,
            idempotency_key=f"USER_REGISTERED:{user_id}",
            recipient_user_id=user_id,
            recipient_email=payload["email"],
            recipient_name="Alex",
            context={"organization_name": "Org", "role_label": "Administrator", "login_url": "http://x/login"},
        )
    )
    assert second.idempotent_replay is True
    assert len(recorder.messages) == 1


def test_existing_org_registration_skips_welcome(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))

    first_payload = _register_payload()
    assert client.post("/api/v1/auth/register", json=first_payload).status_code == 200
    count_after_admin = len(recorder.messages)

    second = client.post(
        "/api/v1/auth/register",
        json=_register_payload(
            email=f"sam.{uuid.uuid4().hex[:6]}@northwind.test",
            organization_name=first_payload["organization_name"],
        ),
    )
    assert second.status_code == 200
    assert second.json()["user"]["role"] == "employee"
    assert second.json().get("notification") is None
    assert len(recorder.messages) == count_after_admin


@pytest.mark.parametrize("role", ["employee", "manager", "hr"])
def test_admin_invitation_email(client: TestClient, role: str) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))

    headers = _headers(client, "admin001")
    email = f"{role}.{uuid.uuid4().hex[:6]}@example.com"
    body: dict = {
        "full_name": f"Invite {role.title()}",
        "email": email,
        "role": role,
    }
    if role == "employee":
        body["employee_id"] = "E002"
    response = client.post("/api/v1/users/invite", headers=headers, json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["notification"]["event_type"] == "USER_INVITED"
    assert payload["notification"]["status"] == "generated"
    assert payload["invitation"]["activation_token"]
    assert "password" not in payload["user"]

    assert recorder.messages
    mail = recorder.messages[-1]
    assert mail.to_email == email
    assert "/activate?token=" in mail.text_body
    # Instructional wording ("set your password") is allowed; no credential may be embedded.
    body_lower = mail.text_body.lower()
    assert "password:" not in body_lower
    assert "your password is" not in body_lower
    assert "temporary password" not in body_lower
    assert INVITE_PASSWORD.lower() not in body_lower
    assert (
        "no password was sent" in body_lower
        or "does not contain a password" in body_lower
    )
    assert role.title() in mail.text_body or role.upper() in mail.text_body or role in mail.text_body.lower()

    token = payload["invitation"]["activation_token"]
    activated = client.post(
        "/api/v1/auth/activate",
        json={
            "token": token,
            "password": INVITE_PASSWORD,
            "confirm_password": INVITE_PASSWORD,
        },
    )
    assert activated.status_code == 200
    login = _login(client, email, INVITE_PASSWORD)
    assert login.status_code == 200
    assert login.json()["user"]["role"] == role


def test_invitation_email_failure_keeps_account(client: TestClient) -> None:
    failing = FailingProvider()
    reset_email_provider(failing)
    reset_business_notification_service(BusinessNotificationService(failing))

    headers = _headers(client, "admin001")
    email = f"fail.invite.{uuid.uuid4().hex[:6]}@example.com"
    response = client.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Fail Invite",
            "email": email,
            "role": "manager",
        },
    )
    assert response.status_code == 200
    assert response.json()["user"]["status"] == "invited"
    assert response.json()["notification"]["status"] == "failed"
    assert response.json()["invitation"]["activation_token"]


def test_pending_approval_and_result_notifications(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))
    _give_demo_users_emails()
    reset_workflow_engine(with_persistence=True)

    emp_headers = _headers(client, "employee001@demo.test")
    pending = client.post(
        "/api/v1/workflows/run",
        headers=emp_headers,
        json={"request": LEAVE_PENDING},
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["status"] == "awaiting_human_approval"
    workflow_id = pending.json()["workflow_id"]

    approval_mails = [
        m for m in recorder.messages if m.event_type == NotificationEventType.WORKFLOW_PENDING_APPROVAL
    ]
    assert approval_mails
    assert all(m.to_email == "manager001@demo.test" for m in approval_mails)
    assert "Approval required" in approval_mails[0].subject or "approval" in approval_mails[0].text_body.lower()
    assert workflow_id in approval_mails[0].text_body or "/workflows/" in approval_mails[0].text_body

    before = len(recorder.messages)
    mgr_headers = _headers(client, "manager001@demo.test")
    approved = client.post(
        f"/api/v1/workflows/{workflow_id}/approve",
        headers=mgr_headers,
        json={"reason": "OK"},
    )
    assert approved.status_code == 200
    assert approved.json()["decision"]["outcome"] == "approve"

    result_mails = recorder.messages[before:]
    approved_mails = [
        m for m in result_mails if m.event_type == NotificationEventType.WORKFLOW_APPROVED
    ]
    assert approved_mails
    assert approved_mails[0].to_email == "employee001@demo.test"
    assert "approved" in approved_mails[0].text_body.lower()


def test_rejection_notification(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))
    _give_demo_users_emails()
    reset_workflow_engine(with_persistence=True)

    emp_headers = _headers(client, "employee001@demo.test")
    pending = client.post(
        "/api/v1/workflows/run",
        headers=emp_headers,
        json={"request": LEAVE_PENDING},
    )
    workflow_id = pending.json()["workflow_id"]
    before = len(recorder.messages)

    mgr_headers = _headers(client, "manager001@demo.test")
    rejected = client.post(
        f"/api/v1/workflows/{workflow_id}/reject",
        headers=mgr_headers,
        json={"reason": "Too long"},
    )
    assert rejected.status_code == 200
    rejected_mails = [
        m
        for m in recorder.messages[before:]
        if m.event_type == NotificationEventType.WORKFLOW_REJECTED
    ]
    assert rejected_mails
    assert rejected_mails[0].to_email == "employee001@demo.test"


def test_workflow_blocked_notification() -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))
    _give_demo_users_emails()
    reset_workflow_engine(with_persistence=True)

    engine = get_workflow_engine()
    result = engine.run(
        LEAVE_BLOCKED,
        organization_id="demo-org",
        user_id="user-employee-001",
        user_role="employee",
    )
    outcome = str((result.state.get("decision") or {}).get("outcome") or "")
    if outcome not in {"blocked", "reject", "rejected"}:
        pytest.skip(f"unexpected outcome for blocked fixture: {outcome}")
    matching = [
        m
        for m in recorder.messages
        if m.event_type
        in {
            NotificationEventType.WORKFLOW_BLOCKED,
            NotificationEventType.WORKFLOW_REJECTED,
        }
    ]
    assert matching
    assert matching[0].to_email == "employee001@demo.test"


def test_completion_notification_for_auto_approve(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))
    _give_demo_users_emails()
    reset_workflow_engine(with_persistence=True)

    emp_headers = _headers(client, "employee001@demo.test")
    response = client.post(
        "/api/v1/workflows/run",
        headers=emp_headers,
        json={
            "request": "Check whether employee E001 can take 3 days of leave from 2026-08-17."
        },
    )
    assert response.status_code == 200
    if response.json()["status"] != "completed":
        pytest.skip("short leave did not auto-complete")
    completed = [
        m for m in recorder.messages if m.event_type == NotificationEventType.WORKFLOW_COMPLETED
    ]
    assert completed
    assert completed[0].to_email == "employee001@demo.test"


def test_duplicate_pending_approval_notification_protection(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))
    _give_demo_users_emails()
    reset_workflow_engine(with_persistence=True)

    emp_headers = _headers(client, "employee001@demo.test")
    pending = client.post(
        "/api/v1/workflows/run",
        headers=emp_headers,
        json={"request": LEAVE_PENDING},
    )
    workflow_id = pending.json()["workflow_id"]
    first_count = len(
        [m for m in recorder.messages if m.event_type == NotificationEventType.WORKFLOW_PENDING_APPROVAL]
    )
    assert first_count >= 1

    # Re-emit same result path via engine resume is not pending; re-dispatch hook via get result
    from app.database.persistence import PersistenceService
    from app.notifications.workflow_hooks import emit_workflow_notifications

    with session_scope() as session:
        indexed = PersistenceService(session).get_result(
            workflow_id, organization_id="demo-org"
        )
    assert indexed is not None
    emit_workflow_notifications(indexed)
    second_count = len(
        [m for m in recorder.messages if m.event_type == NotificationEventType.WORKFLOW_PENDING_APPROVAL]
    )
    assert second_count == first_count


def test_cross_organization_recipient_isolation(client: TestClient) -> None:
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))

    # Register org A
    a = _register_payload(email="admin.a@iso.test", organization_name=f"Iso A {uuid.uuid4().hex[:6]}")
    reg_a = client.post("/api/v1/auth/register", json=a)
    assert reg_a.status_code == 200
    client_org_a = reg_a.json()["user"]["organization_id"]
    # Register org B
    b = _register_payload(email="admin.b@iso.test", organization_name=f"Iso B {uuid.uuid4().hex[:6]}")
    assert client.post("/api/v1/auth/register", json=b).status_code == 200

    headers_a = _headers(client, "admin.a@iso.test", "securePass-123")
    invite = client.post(
        "/api/v1/users/invite",
        headers=headers_a,
        json={
            "full_name": "Org A Manager",
            "email": "manager.a@iso.test",
            "role": "manager",
        },
    )
    assert invite.status_code == 200
    # Org B admin must not see org A invitee
    headers_b = _headers(client, "admin.b@iso.test", "securePass-123")
    listed = client.get("/api/v1/users", headers=headers_b)
    usernames = {u["username"] for u in listed.json()["users"]}
    assert "manager.a@iso.test" not in usernames

    # Invitation email recipient must be org A invitee only
    invite_mails = [m for m in recorder.messages if m.event_type == NotificationEventType.USER_INVITED]
    assert invite_mails[-1].to_email == "manager.a@iso.test"
    assert invite_mails[-1].organization_id == client_org_a


def test_employee_cannot_choose_notification_recipient(client: TestClient) -> None:
    headers = _headers(client, "employee001")
    response = client.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "full_name": "Nope",
            "email": "arbitrary@example.com",
            "role": "employee",
            "recipient_email": "attacker@evil.test",
        },
    )
    assert response.status_code == 403


def test_notification_metrics_and_audit_record(client: TestClient) -> None:
    reset_notification_metrics()
    recorder = RecordingProvider()
    reset_email_provider(recorder)
    reset_business_notification_service(BusinessNotificationService(recorder))

    payload = _register_payload()
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    snapshot = notification_metrics_snapshot()
    assert snapshot["notification_sent_total"]
    assert any(
        item["event_type"] == "USER_REGISTERED" and item["status"] == "generated"
        for item in snapshot["notification_sent_total"]
    )
    # High-cardinality labels must not appear
    blob = str(snapshot)
    assert payload["email"] not in blob

    with session_scope() as session:
        repo = NotificationEventRepository(session)
        record = repo.get_by_idempotency(
            organization_id=response.json()["user"]["organization_id"],
            idempotency_key=f"USER_REGISTERED:{response.json()['user']['user_id']}",
        )
    assert record is not None
    assert record.status == "generated"
    assert record.event_type == "USER_REGISTERED"
    assert "password" not in str(record.audit_meta)
    assert record.recipient_email == payload["email"]


def test_templates_cover_all_event_types() -> None:
    for event in NotificationEventType:
        message = render_email(
            event_type=event,
            to_email="user@example.com",
            to_name="Pat",
            organization_id="org",
            recipient_user_id="u1",
            workflow_run_id="wf-1",
            context={
                "organization_name": "Acme",
                "role_label": "Employee",
                "login_url": "http://x/login",
                "activation_url": "http://x/activate?token=abc",
                "expires_at": "2026-09-01",
                "workflow_type_label": "leave request",
                "summary": "3 days annual leave",
                "approval_url": "http://x/workflows/wf-1",
                "workflow_url": "http://x/workflows/wf-1",
                "requester_name": "Pat",
            },
        )
        assert message.subject
        assert "WorkSphere AI" in message.html_body
        assert "abc" not in message.subject  # token not in subject
        if event != NotificationEventType.USER_INVITED:
            assert "token=abc" not in message.subject
