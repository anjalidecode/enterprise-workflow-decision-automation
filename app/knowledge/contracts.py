"""Knowledge document and search-hit models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """One searchable chunk from the curated knowledge corpus.

    organization_id empty means global/system knowledge available to all orgs.
    Non-empty organization_id means company-specific knowledge for that tenant only.
    """

    document_id: str
    title: str
    content: str
    workflow_type: str
    doc_type: str
    source_path: str
    organization_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeHit(BaseModel):
    """A ranked passage returned by KnowledgeStore.search."""

    document_id: str
    title: str
    content: str
    score: float
    workflow_type: str
    doc_type: str
    source_path: str
    organization_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
