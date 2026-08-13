"""Human approval endpoints — resume via WorkflowEngine only."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import (
    EngineDep,
    IndexDep,
    OrganizationIdQuery,
    RequestIdDep,
)
from app.api.errors import APIError
from app.api.schemas.approvals import ApprovalRequest
from app.api.schemas.workflows import WorkflowRunResponse
from app.api.serializers import to_run_response
from app.workflows.contracts import ApprovalDecision
from app.workflows.errors import WorkflowResumeError

router = APIRouter(tags=["Approvals"])


def _ensure_org_owns_run(index: IndexDep, workflow_id: str, organization_id: str) -> None:
    indexed = index.get(workflow_id, organization_id=organization_id)
    if indexed is None:
        raise APIError(
            status_code=404,
            code="WORKFLOW_NOT_FOUND",
            message=(
                f"Workflow '{workflow_id}' was not found for organization "
                f"'{organization_id}'."
            ),
        )


def _resume(
    *,
    workflow_id: str,
    organization_id: str,
    body: ApprovalRequest,
    approved: bool,
    engine: EngineDep,
    index: IndexDep,
    request_id: str,
) -> WorkflowRunResponse:
    _ensure_org_owns_run(index, workflow_id, organization_id)
    try:
        result = engine.resume(
            workflow_id,
            ApprovalDecision(
                approved=approved,
                decided_by=body.user_id,
                comment=body.reason,
            ),
        )
    except WorkflowResumeError as exc:
        raise APIError(
            status_code=409,
            code="WORKFLOW_NOT_RESUMABLE",
            message=str(exc),
        ) from exc

    # Ensure resumed result remains organization-scoped in the index.
    result_org = str((result.state or {}).get("organization_id") or "")
    if result_org != organization_id:
        raise APIError(
            status_code=404,
            code="WORKFLOW_NOT_FOUND",
            message=(
                f"Workflow '{workflow_id}' was not found for organization "
                f"'{organization_id}'."
            ),
        )
    index.put(result)
    return to_run_response(result, request_id=request_id)


@router.post(
    "/workflows/{workflow_id}/approve",
    response_model=WorkflowRunResponse,
    summary="Approve a paused workflow",
    description=(
        "Calls WorkflowEngine.resume(approved=True). No new approval logic. "
        "organization_id query param enforces isolation (dev context until 5B)."
    ),
)
def approve_workflow(
    workflow_id: str,
    body: ApprovalRequest,
    organization_id: OrganizationIdQuery,
    engine: EngineDep,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    return _resume(
        workflow_id=workflow_id,
        organization_id=organization_id,
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
    organization_id: OrganizationIdQuery,
    engine: EngineDep,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    return _resume(
        workflow_id=workflow_id,
        organization_id=organization_id,
        body=body,
        approved=False,
        engine=engine,
        index=index,
        request_id=request_id,
    )
