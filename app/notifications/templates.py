"""WorkSphere AI email templates — structured data in, no business decisions invented."""

from __future__ import annotations

from typing import Any

from app.notifications.models import EmailMessage, NotificationEventType

BRAND = "WorkSphere AI"
TAGLINE = "AI-Powered HR Workflow & Decision Automation"


def _html_shell(*, title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#1a1a1a;line-height:1.5;margin:0;padding:24px;background:#f6f7f9;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;padding:28px 32px;border:1px solid #e5e7eb;">
    <p style="margin:0 0 4px;font-size:20px;font-weight:700;letter-spacing:-0.02em;">{BRAND}</p>
    <p style="margin:0 0 24px;font-size:12px;color:#6b7280;">{TAGLINE}</p>
    {body_html}
    <p style="margin:28px 0 0;font-size:12px;color:#9ca3af;">This message was sent by {BRAND}. Do not reply with passwords or secrets.</p>
  </div>
</body>
</html>"""


def _link(url: str, label: str | None = None) -> str:
    text = label or url
    return f'<p style="margin:16px 0;"><a href="{url}" style="color:#0f766e;">{text}</a></p>'


def render_email(
    *,
    event_type: NotificationEventType,
    to_email: str,
    to_name: str,
    organization_id: str,
    recipient_user_id: str,
    workflow_run_id: str,
    context: dict[str, Any],
) -> EmailMessage:
    """Render a professional email from event type + safe context."""

    name = (to_name or context.get("recipient_name") or "there").strip()
    org_name = str(context.get("organization_name") or organization_id or "your organization")
    role = str(context.get("role_label") or context.get("role") or "")
    login_url = str(context.get("login_url") or "")
    activation_url = str(context.get("activation_url") or "")
    approval_url = str(context.get("approval_url") or "")
    workflow_url = str(context.get("workflow_url") or "")
    workflow_type = str(context.get("workflow_type_label") or context.get("workflow_type") or "workflow")
    requester = str(context.get("requester_name") or "A teammate")
    summary = str(context.get("summary") or "")
    expires_at = str(context.get("expires_at") or "")

    if event_type == NotificationEventType.USER_REGISTERED:
        subject = f"Welcome to {BRAND}"
        text = "\n".join(
            [
                f"Welcome to {BRAND}",
                TAGLINE,
                "",
                f"Hi {name},",
                "",
                f"Your administrator account for {org_name} has been created.",
                f"Assigned role: {role or 'Administrator'}",
                "",
                f"Sign in: {login_url}" if login_url else "",
                "",
                "You can invite teammates and start HR workflows from the dashboard.",
            ]
        ).strip()
        html = _html_shell(
            title=subject,
            body_html=(
                f"<h1 style='font-size:18px;'>Welcome, {name}</h1>"
                f"<p>Your administrator account for <strong>{org_name}</strong> is ready.</p>"
                f"<p>Assigned role: <strong>{role or 'Administrator'}</strong></p>"
                + (_link(login_url, "Sign in to WorkSphere AI") if login_url else "")
                + "<p>Invite teammates and start HR workflows from your dashboard.</p>"
            ),
        )
    elif event_type == NotificationEventType.USER_INVITED:
        subject = f"You're invited to {BRAND}"
        text = "\n".join(
            [
                f"You're invited to {BRAND}",
                "",
                f"Hi {name},",
                "",
                f"You have been invited to join {org_name} on {BRAND}.",
                f"Assigned role: {role}",
                f"Activate your account: {activation_url}" if activation_url else "",
                f"This invitation expires: {expires_at}" if expires_at else "",
                "",
                "Open the link, set your password, then sign in. No password was sent in this email.",
            ]
        ).strip()
        html = _html_shell(
            title=subject,
            body_html=(
                f"<h1 style='font-size:18px;'>You're invited, {name}</h1>"
                f"<p>Join <strong>{org_name}</strong> on {BRAND}.</p>"
                f"<p>Assigned role: <strong>{role}</strong></p>"
                + (_link(activation_url, "Activate your account") if activation_url else "")
                + (f"<p>This invitation expires: {expires_at}</p>" if expires_at else "")
                + "<p>Set your own password on the activation page. This email does not contain a password.</p>"
            ),
        )
    elif event_type == NotificationEventType.WORKFLOW_PENDING_APPROVAL:
        subject = f"Approval required — {workflow_type}"
        text = "\n".join(
            [
                f"{BRAND}: approval required",
                "",
                f"Hi {name},",
                "",
                f"{requester} submitted a {workflow_type} that needs your approval.",
                f"Summary: {summary}" if summary else "",
                f"Review: {approval_url or workflow_url}",
            ]
        ).strip()
        html = _html_shell(
            title=subject,
            body_html=(
                f"<h1 style='font-size:18px;'>Approval required</h1>"
                f"<p><strong>{requester}</strong> submitted a <strong>{workflow_type}</strong> request.</p>"
                + (f"<p>{summary}</p>" if summary else "")
                + (_link(approval_url or workflow_url, "Open approval page") if (approval_url or workflow_url) else "")
            ),
        )
    elif event_type == NotificationEventType.WORKFLOW_APPROVED:
        subject = f"Your {workflow_type} was approved"
        text = "\n".join(
            [
                f"{BRAND}: request approved",
                "",
                f"Hi {name},",
                "",
                f"Your {workflow_type} has been approved.",
                f"Summary: {summary}" if summary else "",
                f"Details: {workflow_url}" if workflow_url else "",
            ]
        ).strip()
        html = _html_shell(
            title=subject,
            body_html=(
                f"<h1 style='font-size:18px;'>Request approved</h1>"
                f"<p>Your <strong>{workflow_type}</strong> has been approved.</p>"
                + (f"<p>{summary}</p>" if summary else "")
                + (_link(workflow_url, "View workflow") if workflow_url else "")
            ),
        )
    elif event_type == NotificationEventType.WORKFLOW_REJECTED:
        subject = f"Your {workflow_type} was rejected"
        text = "\n".join(
            [
                f"{BRAND}: request rejected",
                "",
                f"Hi {name},",
                "",
                f"Your {workflow_type} has been rejected.",
                f"Summary: {summary}" if summary else "",
                f"Details: {workflow_url}" if workflow_url else "",
            ]
        ).strip()
        html = _html_shell(
            title=subject,
            body_html=(
                f"<h1 style='font-size:18px;'>Request rejected</h1>"
                f"<p>Your <strong>{workflow_type}</strong> has been rejected.</p>"
                + (f"<p>{summary}</p>" if summary else "")
                + (_link(workflow_url, "View workflow") if workflow_url else "")
            ),
        )
    elif event_type == NotificationEventType.WORKFLOW_BLOCKED:
        subject = f"Your {workflow_type} is blocked"
        text = "\n".join(
            [
                f"{BRAND}: workflow blocked",
                "",
                f"Hi {name},",
                "",
                f"Your {workflow_type} could not proceed and is blocked.",
                f"Summary: {summary}" if summary else "",
                f"Details: {workflow_url}" if workflow_url else "",
            ]
        ).strip()
        html = _html_shell(
            title=subject,
            body_html=(
                f"<h1 style='font-size:18px;'>Workflow blocked</h1>"
                f"<p>Your <strong>{workflow_type}</strong> is blocked and needs attention.</p>"
                + (f"<p>{summary}</p>" if summary else "")
                + (_link(workflow_url, "View workflow") if workflow_url else "")
            ),
        )
    else:  # WORKFLOW_COMPLETED
        subject = f"Your {workflow_type} is complete"
        text = "\n".join(
            [
                f"{BRAND}: workflow completed",
                "",
                f"Hi {name},",
                "",
                f"Your {workflow_type} has completed.",
                f"Summary: {summary}" if summary else "",
                f"Details: {workflow_url}" if workflow_url else "",
            ]
        ).strip()
        html = _html_shell(
            title=subject,
            body_html=(
                f"<h1 style='font-size:18px;'>Workflow completed</h1>"
                f"<p>Your <strong>{workflow_type}</strong> has completed successfully.</p>"
                + (f"<p>{summary}</p>" if summary else "")
                + (_link(workflow_url, "View workflow") if workflow_url else "")
            ),
        )

    return EmailMessage(
        to_email=to_email,
        to_name=name,
        subject=subject,
        text_body=text,
        html_body=html,
        event_type=event_type,
        organization_id=organization_id,
        recipient_user_id=recipient_user_id,
        workflow_run_id=workflow_run_id,
        metadata={
            "organization_name": org_name,
            "workflow_type": workflow_type,
        },
    )
