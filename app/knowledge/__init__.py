"""Knowledge corpus and retriever. Agents must use the memory facade."""

from app.knowledge.indexer import index_knowledge_corpus
from app.knowledge.store import get_knowledge_store, reset_knowledge_store

__all__ = ["get_knowledge_store", "index_knowledge_corpus", "reset_knowledge_store"]
