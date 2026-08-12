"""Build or refresh the knowledge index from the corpus."""

from __future__ import annotations

from app.knowledge.contracts import KnowledgeDocument
from app.knowledge.corpus import load_knowledge_documents
from app.knowledge.store import KnowledgeStore, get_knowledge_store


def index_knowledge_corpus() -> list[KnowledgeDocument]:
    """Reload handbook documents into the process-level knowledge store."""

    documents = load_knowledge_documents()
    get_knowledge_store().reset(documents)
    return documents


def build_knowledge_store() -> KnowledgeStore:
    return KnowledgeStore(load_knowledge_documents())
