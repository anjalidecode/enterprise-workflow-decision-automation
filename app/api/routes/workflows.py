"""Workflow REST endpoints — thin facade over WorkflowEngine."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.dependencies import (
    EngineDep,
    IndexDep,
    OrganizationIdQuery,
    RequestIdDep,
)
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
from app.workflows.registry import get_workflow_registry

router = APIRouter(tags=["Workflows"])


def _require_indexed(
    index: IndexDep,
    workflow_id: str,
    organization_id: str,
):
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


@router.get(
    "/workflows/types",
    response_model=WorkflowTypeResponse,
    summary="List registered workflow types",
    description="Returns workflow types from WorkflowRegistry (not hardcoded).",
)
def list_workflow_types() -> WorkflowTypeResponse:
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
        "Calls WorkflowEngine.run() only. organization_id / user_id / user_role "
        "are development context fields until Module 5B authentication."
    ),
)
def run_workflow(
    body: WorkflowRunRequest,
    engine: EngineDep,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    result = engine.run(
        body.request,
        organization_id=body.organization_id,
        user_id=body.user_id,
        user_role=body.user_role,
        workflow_type=body.workflow_type,
        request_id=request_id or None,
    )
    index.put(result)
    return to_run_response(result, request_id=request_id)


@router.get(
    "/workflows",
    response_model=WorkflowListResponse,
    summary="List workflow runs",
    description=(
        "Lists runs recorded in the API-layer in-memory execution index for this "
        "process. Not durable storage. Filtered by organization_id."
    ),
)
def list_workflows(
    organization_id: OrganizationIdQuery,
    index: IndexDep,
    workflow_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WorkflowListResponse:
    items, total = index.list(
        organization_id=organization_id,
        workflow_type=workflow_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return WorkflowListResponse(
        workflows=[to_summary(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowRunResponse,
    summary="Get a workflow run",
    description=(
        "Retrieve a WorkflowResult from the in-memory API index. "
        "Requires organization_id for isolation. Not a database lookup."
    ),
)
def get_workflow(
    workflow_id: str,
    organization_id: OrganizationIdQuery,
    index: IndexDep,
    request_id: RequestIdDep,
) -> WorkflowRunResponse:
    result = _require_indexed(index, workflow_id, organization_id)
    return to_run_response(result, request_id=request_id)


@router.get(
    "/workflows/{workflow_id}/audit",
    response_model=WorkflowAuditResponse,
    summary="Get workflow audit snapshot",
    description="Returns the existing WorkflowAuditSnapshot via a Pydantic API schema.",
)
def get_workflow_audit(
    workflow_id: str,
    organization_id: OrganizationIdQuery,
    index: IndexDep,
) -> WorkflowAuditResponse:
    result = _require_indexed(index, workflow_id, organization_id)
    return to_audit_response(result)


@router.get(
    "/workflows/{workflow_id}/metrics",
    response_model=WorkflowMetricsResponse,
    summary="Get workflow run metrics",
    description="Returns the existing WorkflowRunMetrics via a Pydantic API schema.",
)
def get_workflow_metrics(
    workflow_id: str,
    organization_id: OrganizationIdQuery,
    index: IndexDep,
) -> WorkflowMetricsResponse:
    result = _require_indexed(index, workflow_id, organization_id)
    return to_metrics_response(result)
