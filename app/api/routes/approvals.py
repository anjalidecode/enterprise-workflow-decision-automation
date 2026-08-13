"""Human approval endpoints — resume via WorkflowEngine only."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import EngineDep, IndexDep, RequestIdDep
from app.api.errors import APIError
from app.api.schemas.approvals import ApprovalRequest
from app.api.schemas.workflows import WorkflowRunResponse
from app.api.serializers import to_run_response
from app.auth.dependencies import CurrentUser
from app.auth.permissions import assert_can_approve
from app.workflows.contracts import ApprovalDecision
from app.workflows.errors import WorkflowResumeError

router = APIRouter(tags=["Approvals"])


def _resume(
    *,
    workflow_id: str,
    user: CurrentUser,
    body: ApprovalRequest,
    approved: bool,
    engine: EngineDep,
    index: IndexDep,
    request_id: str,
) -> WorkflowRunResponse:
    indexed = index.get(workflow_id, organization_id=user.organization_id)
    if indexed is None:
        raise APIError(
            status_code=404,
            code="WORKFLOW_NOT_FOUND",
            message=(
                f"Workflow '{workflow_id}' was not found for organization "
                f"'{user.organization_id}'."
            ),
        )
    assert_can_approve(user, indexed)
    try:
        result = engine.resume(
            workflow_id,
            ApprovalDecision(
                approved=approved,
                decided_by=user.user_id,
                comment=body.reason,
            ),
        )
    except WorkflowResumeError as exc:
        raise APIError(
            status_code=409,
            code="WORKFLOW_NOT_RESUMABLE",
            message=str(exc),
        ) from exc

    result_org = str((result.state or {}).get("organization_id") or "")
    if result_org != user.organization_id:
        raise APIError(
            status_code=404,
            code="WORKFLOW_NOT_FOUND",
            message=(
                f"Workflow '{workflow_id}' was not found for organization "
                f"'{user.organization_id}'."
            ),
        )
    index.put(result)
    return to_run_response(result, request_id=request_id)


@router.post(
    "/workflows/{workflow_id}/approve",
    response_model=WorkflowRunResponse,
    summary="Approve a paused workflow",
    description=(
        "Calls WorkflowEngine.resume(approved=True). Approver identity and role "
        "come from the JWT — request body cannot spoof user_role."
    ),
)
def approve_workflow(
    workflow_id: str,
    body: ApprovalRequest,
    user: CurrentUser,
    engine: EngineDep,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    return _resume(
        workflow_id=workflow_id,
        user=user,
        body=body,
        approved=True,
        engine=engine,
        index=index,
        request_id=request_id,
    )


@router.post(
    "/workflows/{workflow_id}/reject",
    response_model=WorkflowRunResponse,
    summary="Reject a paused workflow",
    description=(
        "Calls WorkflowEngine.resume(approved=False). Uses existing platform behavior."
    ),
)
def reject_workflow(
    workflow_id: str,
    body: ApprovalRequest,
    user: CurrentUser,
    engine: EngineDep,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    return _resume(
        workflow_id=workflow_id,
        user=user,
        body=body,
        approved=False,
        engine=engine,
        index=index,
        request_id=request_id,
    )
