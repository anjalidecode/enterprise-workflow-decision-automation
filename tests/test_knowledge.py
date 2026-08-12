from app.knowledge.indexer import index_knowledge_corpus
from app.knowledge.store import KnowledgeStore
from app.memory.facade import search_knowledge
from app.orchestration.state import create_initial_state


def test_leave_handbook_is_indexed() -> None:
    documents = index_knowledge_corpus()
    assert documents
    assert any("handbook" in item.source_path for item in documents)


def test_leave_query_returns_relevant_hit_without_api_key() -> None:
    store = KnowledgeStore()
    hits = store.search("manager approval for long leave", workflow_type="leave_attendance")
    assert hits
    assert hits[0].score > 0
    combined = " ".join(hit.content.lower() + hit.title.lower() for hit in hits)
    assert "approval" in combined
    assert "leave" in combined


def test_knowledge_filters() -> None:
    store = KnowledgeStore()
    leave_hits = store.search("leave process", workflow_type="leave_attendance", doc_type="handbook")
    other_hits = store.search("leave process", workflow_type="recruitment")
    assert leave_hits
    assert other_hits == []


def test_facade_knowledge_search_records_access() -> None:
    state = create_initial_state("Check whether employee E001 can take 8 days of leave from 2026-08-17.")
    state["workflow_type"] = "leave_attendance"
    hits, patch = search_knowledge(state, agent="policy", query="manager approval for long leave")
    assert hits
    assert patch["memory_accesses"][0]["layer"] == "knowledge"
    assert patch["memory_accesses"][0]["operation"] == "read"
