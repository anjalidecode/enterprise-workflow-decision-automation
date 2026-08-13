"""Workflow REST endpoints — thin facade over WorkflowEngine."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.dependencies import EngineDep, IndexDep, RequestIdDep
from app.api.errors import APIError
from app.api.schemas.workflows import (
    WorkflowAuditResponse,
    WorkflowListResponse,
    WorkflowMetricsResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowTypeItem,
    WorkflowTypeResponse,
)
from app.api.serializers import (
    to_audit_response,
    to_metrics_response,
    to_run_response,
    to_summary,
)
from app.auth.dependencies import CurrentUser
from app.auth.permissions import (
    assert_can_run_workflow,
    assert_can_view_workflow,
    employee_run_entities,
    filter_results_for_user,
)
from app.workflows.registry import get_workflow_registry

router = APIRouter(tags=["Workflows"])


def _require_indexed(index: IndexDep, workflow_id: str, organization_id: str):
    result = index.get(workflow_id, organization_id=organization_id)
    if result is None:
        raise APIError(
            status_code=404,
            code="WORKFLOW_NOT_FOUND",
            message=(
                f"Workflow '{workflow_id}' was not found for organization "
                f"'{organization_id}'. Results are stored in the in-memory API "
                "index for this process only."
            ),
        )
    return result


def _get_authorized_result(index: IndexDep, workflow_id: str, user: CurrentUser):
    result = _require_indexed(index, workflow_id, user.organization_id)
    assert_can_view_workflow(user, result)
    return result


@router.get(
    "/workflows/types",
    response_model=WorkflowTypeResponse,
    summary="List registered workflow types",
    description="Returns workflow types from WorkflowRegistry. Requires authentication.",
)
def list_workflow_types(_user: CurrentUser) -> WorkflowTypeResponse:
    specs = get_workflow_registry().list_workflows()
    workflows = [
        WorkflowTypeItem(
            workflow_type=spec.workflow_type,
            name=spec.name,
            description=spec.description,
            version=spec.version,
        )
        for spec in sorted(specs, key=lambda item: item.workflow_type)
    ]
    return WorkflowTypeResponse(workflows=workflows)


@router.post(
    "/workflows/run",
    response_model=WorkflowRunResponse,
    summary="Run a workflow",
    description=(
        "Calls WorkflowEngine.run() using authenticated identity from the JWT. "
        "Request-body identity fields are ignored."
    ),
)
def run_workflow(
    body: WorkflowRunRequest,
    user: CurrentUser,
    engine: EngineDep,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    assert_can_run_workflow(
        user,
        request_text=body.request,
        workflow_type=body.workflow_type,
    )
    result = engine.run(
        body.request,
        organization_id=user.organization_id,
        user_id=user.user_id,
        user_role=user.role.value,
        workflow_type=body.workflow_type,
        request_id=request_id or None,
        entities=employee_run_entities(user),
    )
    index.put(result)
    return to_run_response(result, request_id=request_id)


@router.get(
    "/workflows",
    response_model=WorkflowListResponse,
    summary="List workflow runs",
    description=(
        "Lists runs from the process-local API index for the authenticated organization, "
        "filtered by role ownership rules."
    ),
)
def list_workflows(
    user: CurrentUser,
    index: IndexDep,
    workflow_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WorkflowListResponse:
    items, _total = index.list(
        organization_id=user.organization_id,
        workflow_type=workflow_type,
        status=status,
        limit=10_000,
        offset=0,
    )
    visible = filter_results_for_user(user, items)
    total = len(visible)
    sliced = visible[offset : offset + limit]
    return WorkflowListResponse(
        workflows=[to_summary(item) for item in sliced],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowRunResponse,
    summary="Get a workflow run",
    description="Org-scoped retrieval from the in-memory API index with ownership checks.",
)
def get_workflow(
    workflow_id: str,
    user: CurrentUser,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    result = _get_authorized_result(index, workflow_id, user)
    return to_run_response(result, request_id=request_id)


@router.get(
    "/workflows/{workflow_id}/audit",
    response_model=WorkflowAuditResponse,
    summary="Get workflow audit snapshot",
)
def get_workflow_audit(
    workflow_id: str,
    user: CurrentUser,
    index: IndexDep,
) -> WorkflowAuditResponse:
    result = _get_authorized_result(index, workflow_id, user)
    return to_audit_response(result)


@router.get(
    "/workflows/{workflow_id}/metrics",
    response_model=WorkflowMetricsResponse,
    summary="Get workflow run metrics",
)
def get_workflow_metrics(
    workflow_id: str,
    user: CurrentUser,
    index: IndexDep,
) -> WorkflowMetricsResponse:
    result = _get_authorized_result(index, workflow_id, user)
    return to_metrics_response(result)
