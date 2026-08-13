"""Workflow run repository — always scoped by organization_id."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.workflow import WorkflowRun


class WorkflowRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_workflow_id(
        self,
        workflow_id: str,
        *,
        organization_id: str,
    ) -> WorkflowRun | None:
        stmt = (
            select(WorkflowRun)
            .options(
                selectinload(WorkflowRun.decision),
                selectinload(WorkflowRun.approval),
                selectinload(WorkflowRun.audit),
                selectinload(WorkflowRun.metrics),
            )
            .where(
                WorkflowRun.workflow_id == workflow_id,
                WorkflowRun.organization_id == organization_id,
            )
        )
        return self._session.scalars(stmt).first()

    def list_for_organization(
        self,
        *,
        organization_id: str,
        workflow_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WorkflowRun], int]:
        filters = [WorkflowRun.organization_id == organization_id]
        if workflow_type:
            filters.append(WorkflowRun.workflow_type == workflow_type)
        if status:
            filters.append(WorkflowRun.status == status)

        count_stmt = select(WorkflowRun).where(*filters)
        all_rows = list(self._session.scalars(count_stmt).all())
        total = len(all_rows)

        stmt = (
            select(WorkflowRun)
            .options(
                selectinload(WorkflowRun.decision),
                selectinload(WorkflowRun.approval),
                selectinload(WorkflowRun.audit),
                selectinload(WorkflowRun.metrics),
            )
            .where(*filters)
            .order_by(WorkflowRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all()), total

    def upsert_run(
        self,
        *,
        workflow_id: str,
        organization_id: str,
        workflow_type: str,
        user_id: str,
        status: str,
        current_stage: str,
        started_at: datetime | None,
        completed_at: datetime | None,
        outcome: str,
        requires_human_approval: bool,
        result_snapshot: dict[str, Any],
        final_response: str,
    ) -> WorkflowRun:
        existing = self.get_by_workflow_id(workflow_id, organization_id=organization_id)
        if existing is None:
            # Guard against cross-org collision on the same workflow_id.
            collision = self._session.scalars(
                select(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id)
            ).first()
            if collision is not None and collision.organization_id != organization_id:
                # Do not update another tenant's row; treat as not found for this org.
                raise PermissionError(
                    "Workflow identifier is owned by another organization."
                )
            run = WorkflowRun(
                workflow_id=workflow_id,
                organization_id=organization_id,
                workflow_type=workflow_type,
                user_id=user_id,
                status=status,
                current_stage=current_stage,
                started_at=started_at,
                completed_at=completed_at,
                outcome=outcome,
                requires_human_approval=requires_human_approval,
                result_snapshot=result_snapshot,
                final_response=final_response,
            )
            self._session.add(run)
            self._session.flush()
            return run

        existing.workflow_type = workflow_type
        existing.user_id = user_id
        existing.status = status
        existing.current_stage = current_stage
        existing.started_at = started_at or existing.started_at
        existing.completed_at = completed_at
        existing.outcome = outcome
        existing.requires_human_approval = requires_human_approval
        existing.result_snapshot = result_snapshot
        existing.final_response = final_response
        self._session.flush()
        return existing
