"""Offline lexical knowledge retriever. Replaceable later with a vector store.

Search returns global knowledge plus the requesting organization's documents.
Organization-specific documents must never be returned to another organization.
"""

from __future__ import annotations

import re
from typing import Any

from app.knowledge.contracts import KnowledgeDocument, KnowledgeHit
from app.knowledge.corpus import load_knowledge_documents

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _visible_to_organization(document: KnowledgeDocument, organization_id: str) -> bool:
    """Global docs (empty org) are always visible; org docs only to that tenant."""

    doc_org = document.organization_id or ""
    if not doc_org:
        return True
    requested = organization_id or ""
    return bool(requested) and doc_org == requested


class KnowledgeStore:
    """In-process lexical search over curated handbook chunks."""

    def __init__(self, documents: list[KnowledgeDocument] | None = None) -> None:
        self._documents = documents if documents is not None else load_knowledge_documents()

    def reset(self, documents: list[KnowledgeDocument] | None = None) -> None:
        self._documents = documents if documents is not None else load_knowledge_documents()

    def search(
        self,
        query: str,
        *,
        organization_id: str = "",
        workflow_type: str | None = None,
        doc_type: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 3,
    ) -> list[KnowledgeHit]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        extra = filters or {}
        filter_workflow = workflow_type or extra.get("workflow_type")
        filter_doc_type = doc_type if doc_type is not None else extra.get("doc_type")

        hits: list[KnowledgeHit] = []
        for document in self._documents:
            if not _visible_to_organization(document, organization_id):
                continue
            if filter_workflow and document.workflow_type != filter_workflow:
                continue
            if filter_doc_type and document.doc_type != filter_doc_type:
                continue
            doc_tokens = tokenize(f"{document.title} {document.content}")
            overlap = query_tokens & doc_tokens
            if not overlap:
                continue
            score = len(overlap) / len(query_tokens)
            hits.append(
                KnowledgeHit(
                    document_id=document.document_id,
                    title=document.title,
                    content=document.content,
                    score=score,
                    workflow_type=document.workflow_type,
                    doc_type=document.doc_type,
                    source_path=document.source_path,
                    organization_id=document.organization_id,
                    metadata=dict(document.metadata),
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]


_STORE: KnowledgeStore | None = None


def get_knowledge_store() -> KnowledgeStore:
    global _STORE
    if _STORE is None:
        _STORE = KnowledgeStore()
    return _STORE


def reset_knowledge_store() -> KnowledgeStore:
    store = get_knowledge_store()
    store.reset()
    return store
