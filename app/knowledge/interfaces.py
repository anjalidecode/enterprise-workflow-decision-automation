"""KnowledgeStore port. Agents use MemoryFacade; storage backends are swappable."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.knowledge.contracts import KnowledgeHit


@runtime_checkable
class KnowledgeStorePort(Protocol):
    def search(
        self,
        query: str,
        *,
        organization_id: str = "",
        workflow_type: str | None = None,
        doc_type: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 3,
    ) -> list[KnowledgeHit]: ...
