"""Emit workflow lifecycle notification emails from authoritative WorkflowResult state."""

from __future__ import annotations

import logging
from typing import Any

from app.database.session import session_scope
from app.notifications.models import (
    NotificationDispatchResult,
    NotificationEventPayload,
    NotificationEventType,
)
from app.notifications.recipients import resolve_approvers, resolve_user
from app.notifications.service import (
    frontend_url,
    get_business_notification_service,
    workflow_type_label,
)
from app.workflows.contracts import WorkflowResult

logger = logging.getLogger("worksphere.notifications.workflow")


def _summary_from_state(state: dict[str, Any]) -> str:
    decision = state.get("decision") or {}
    rationale = str(decision.get("rationale") or "").strip()
    if rationale:
        return rationale[:400]
    final = str(state.get("final_response") or "").strip()
    return final[:400]


def _requester_name(state: dict[str, Any], recipient_name: str = "") -> str:
    if recipient_name:
        return recipient_name
    initiated = str(state.get("initiated_by") or state.get("user_id") or "").strip()
    return initiated or "A teammate"


def emit_workflow_notifications(result: WorkflowResult) -> list[NotificationDispatchResult]:
    """Side-effect notifications for meaningful business outcomes only.

    Never raises into the workflow engine.
    """

    try:
        return _emit(result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow_notification_hook_failed error=%s", type(exc).__name__)
        return []


def _emit(result: WorkflowResult) -> list[NotificationDispatchResult]:
    state = result.state or {}
    organization_id = str(state.get("organization_id") or "").strip()
    workflow_id = str(state.get("workflow_id") or "").strip()
    if not organization_id or not workflow_id:
        return []

    status = str(state.get("status") or "")
    decision = state.get("decision") or {}
    outcome = str(decision.get("outcome") or "").strip().lower()
    workflow_type = str(state.get("workflow_type") or "")
    wlabel = workflow_type_label(workflow_type)
    summary = _summary_from_state(state)
    metadata = state.get("metadata") or {}
    approval = metadata.get("approval") if isinstance(metadata, dict) else {}
    approval_status = str((approval or {}).get("status") or "").lower()
    required_role = str((approval or {}).get("required_role") or "manager")

    dispatched: list[NotificationDispatchResult] = []
    service = get_business_notification_service()

    with session_scope() as session:
        requester_id = str(state.get("user_id") or "").strip()
        requester = (
            resolve_user(session, user_id=requester_id, organization_id=organization_id)
            if requester_id
            else None
        )

        def _send(
            event_type: NotificationEventType,
            *,
            recipient_user_id: str,
            recipient_email: str,
            recipient_name: str,
            idempotency_suffix: str,
            extra: dict[str, Any] | None = None,
        ) -> None:
            context = {
                "organization_name": (requester.organization_name if requester else organization_id),
                "workflow_type": workflow_type,
                "workflow_type_label": wlabel,
                "summary": summary,
                "workflow_url": frontend_url(f"/workflows/{workflow_id}"),
                "approval_url": frontend_url(f"/workflows/{workflow_id}"),
                "requester_name": _requester_name(
                    state, requester.full_name if requester else ""
                ),
                **(extra or {}),
            }
            # Prefer recipient's org name when available
            if recipient_user_id:
                resolved = resolve_user(
                    session, user_id=recipient_user_id, organization_id=organization_id
                )
                if resolved:
                    context["organization_name"] = resolved.organization_name
            result_item = service.dispatch(
                NotificationEventPayload(
                    event_type=event_type,
                    organization_id=organization_id,
                    idempotency_key=f"{event_type.value}:{workflow_id}:{idempotency_suffix}",
                    recipient_user_id=recipient_user_id,
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    workflow_run_id=workflow_id,
                    context=context,
                ),
                session=session,
            )
            dispatched.append(result_item)

        # Pending approval → authorized approvers
        if status == "awaiting_human_approval" or (
            decision.get("requires_human_approval") and approval_status in {"", "awaiting"}
        ):
            approvers = resolve_approvers(
                session,
                organization_id=organization_id,
                required_role=required_role,
            )
            for approver in approvers:
                _send(
                    NotificationEventType.WORKFLOW_PENDING_APPROVAL,
                    recipient_user_id=approver.user_id,
                    recipient_email=approver.email,
                    recipient_name=approver.full_name,
                    idempotency_suffix=approver.user_id,
                )
            return dispatched

        # Approval / rejection from human resume
        if approval_status == "approved" and requester is not None:
            _send(
                NotificationEventType.WORKFLOW_APPROVED,
                recipient_user_id=requester.user_id,
                recipient_email=requester.email,
                recipient_name=requester.full_name,
                idempotency_suffix="requester",
            )
            return dispatched

        if approval_status == "rejected" and requester is not None:
            _send(
                NotificationEventType.WORKFLOW_REJECTED,
                recipient_user_id=requester.user_id,
                recipient_email=requester.email,
                recipient_name=requester.full_name,
                idempotency_suffix="requester",
            )
            return dispatched

        # Non-approval terminal outcomes
        if requester is None:
            return dispatched

        if outcome in {"blocked", "block"}:
            _send(
                NotificationEventType.WORKFLOW_BLOCKED,
                recipient_user_id=requester.user_id,
                recipient_email=requester.email,
                recipient_name=requester.full_name,
                idempotency_suffix="blocked",
            )
            return dispatched

        if outcome in {"reject", "rejected"} and status == "completed":
            _send(
                NotificationEventType.WORKFLOW_REJECTED,
                recipient_user_id=requester.user_id,
                recipient_email=requester.email,
                recipient_name=requester.full_name,
                idempotency_suffix="decision",
            )
            return dispatched

        if status == "completed" and outcome in {"approve", "approved", "complete", "completed"}:
            _send(
                NotificationEventType.WORKFLOW_COMPLETED,
                recipient_user_id=requester.user_id,
                recipient_email=requester.email,
                recipient_name=requester.full_name,
                idempotency_suffix="complete",
            )

    return dispatched
