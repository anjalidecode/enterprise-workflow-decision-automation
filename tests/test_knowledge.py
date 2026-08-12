from app.knowledge.contracts import KnowledgeDocument
from app.knowledge.indexer import index_knowledge_corpus
from app.knowledge.store import KnowledgeStore
from app.memory.facade import search_knowledge
from app.orchestration.state import create_initial_state


def test_leave_handbook_is_indexed() -> None:
    documents = index_knowledge_corpus()
    assert documents
    assert any("handbook" in item.source_path for item in documents)
    assert any(item.workflow_type == "leave_attendance" for item in documents)


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
    state["organization_id"] = "org-demo"
    hits, patch = search_knowledge(state, agent="policy", query="manager approval for long leave")
    assert hits
    assert patch["memory_accesses"][0]["layer"] == "knowledge"
    assert patch["memory_accesses"][0]["operation"] == "read"
    assert patch["memory_accesses"][0]["organization_id"] == "org-demo"


def test_organization_knowledge_never_leaks_across_tenants() -> None:
    documents = [
        KnowledgeDocument(
            document_id="global-1",
            title="Global leave process",
            content="Global handbook describes leave process and approval.",
            workflow_type="leave_attendance",
            doc_type="handbook",
            source_path="leave/handbook.md",
            organization_id="",
        ),
        KnowledgeDocument(
            document_id="org-a-1",
            title="Acme leave process",
            content="Acme secret leave process and approval rule.",
            workflow_type="leave_attendance",
            doc_type="handbook",
            source_path="organizations/org-a/leave/handbook.md",
            organization_id="org-a",
        ),
        KnowledgeDocument(
            document_id="org-b-1",
            title="Beta leave process",
            content="Beta secret leave process and approval rule.",
            workflow_type="leave_attendance",
            doc_type="handbook",
            source_path="organizations/org-b/leave/handbook.md",
            organization_id="org-b",
        ),
    ]
    store = KnowledgeStore(documents)
    for_a = store.search(
        "leave process approval",
        organization_id="org-a",
        workflow_type="leave_attendance",
    )
    for_b = store.search(
        "leave process approval",
        organization_id="org-b",
        workflow_type="leave_attendance",
    )
    ids_a = {hit.document_id for hit in for_a}
    ids_b = {hit.document_id for hit in for_b}
    assert "global-1" in ids_a
    assert "org-a-1" in ids_a
    assert "org-b-1" not in ids_a
    assert "global-1" in ids_b
    assert "org-b-1" in ids_b
    assert "org-a-1" not in ids_b
