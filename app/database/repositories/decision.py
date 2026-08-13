"""Decision repository — organization-scoped."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.database.models.decision import DecisionRecord


class DecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_workflow_id(
        self,
        workflow_id: str,
        *,
        organization_id: str,
    ) -> DecisionRecord | None:
        stmt = select(DecisionRecord).where(
            DecisionRecord.workflow_id == workflow_id,
            DecisionRecord.organization_id == organization_id,
        )
        return self._session.scalars(stmt).first()

    def upsert(
        self,
        *,
        workflow_id: str,
        organization_id: str,
        outcome: str,
        rationale: str,
        confidence: float,
        executable: bool,
        requires_human_approval: bool,
        entity_refs: dict[str, Any],
        evidence: list[Any],
        blockers: list[Any],
        warnings: list[Any],
        influenced_by: list[Any],
        decided_at: datetime | None = None,
    ) -> DecisionRecord:
        existing = self.get_by_workflow_id(workflow_id, organization_id=organization_id)
        if existing is None:
            record = DecisionRecord(
                workflow_id=workflow_id,
                organization_id=organization_id,
                outcome=outcome,
                rationale=rationale,
                confidence=confidence,
                executable=executable,
                requires_human_approval=requires_human_approval,
                entity_refs=entity_refs,
                evidence=evidence,
                blockers=blockers,
                warnings=warnings,
                influenced_by=influenced_by,
                decided_at=decided_at or utc_now(),
            )
            self._session.add(record)
            self._session.flush()
            return record

        existing.outcome = outcome
        existing.rationale = rationale
        existing.confidence = confidence
        existing.executable = executable
        existing.requires_human_approval = requires_human_approval
        existing.entity_refs = entity_refs
        existing.evidence = evidence
        existing.blockers = blockers
        existing.warnings = warnings
        existing.influenced_by = influenced_by
        existing.decided_at = decided_at or utc_now()
        self._session.flush()
        return existing
