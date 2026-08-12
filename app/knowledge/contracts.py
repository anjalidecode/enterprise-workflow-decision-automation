"""Knowledge document and search-hit models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """One searchable chunk from the curated knowledge corpus."""

    document_id: str
    title: str
    content: str
    workflow_type: str
    doc_type: str
    source_path: str


class KnowledgeHit(BaseModel):
    """A ranked passage returned by KnowledgeStore.search."""

    document_id: str
    title: str
    content: str
    score: float
    workflow_type: str
    doc_type: str
    source_path: str
    metadata: dict = Field(default_factory=dict)
