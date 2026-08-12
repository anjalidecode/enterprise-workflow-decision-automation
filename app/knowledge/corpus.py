"""Load curated knowledge documents from data/knowledge."""

from __future__ import annotations

from pathlib import Path

from app.knowledge.contracts import KnowledgeDocument

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"

WORKFLOW_TYPE_BY_FOLDER = {
    "leave": "leave_attendance",
    "recruitment": "recruitment",
    "onboarding": "onboarding",
    "performance": "performance",
    "offboarding": "offboarding",
}


def _split_markdown(text: str) -> list[tuple[str, str]]:
    """Split a markdown file into (title, body) sections on level-2 headings."""

    sections: list[tuple[str, str]] = []
    current_title = "Overview"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_title, body))
            current_title = line[3:].strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    body = "\n".join(current_lines).strip()
    if body:
        sections.append((current_title, body))
    return sections


def load_knowledge_documents() -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []
    if not KNOWLEDGE_DIR.exists():
        return documents

    for path in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        relative = path.relative_to(KNOWLEDGE_DIR)
        folder = relative.parts[0] if relative.parts else "general"
        workflow_type = WORKFLOW_TYPE_BY_FOLDER.get(folder, folder)
        text = path.read_text(encoding="utf-8")
        for index, (title, body) in enumerate(_split_markdown(text), start=1):
            documents.append(
                KnowledgeDocument(
                    document_id=f"{path.stem}-{index}",
                    title=title,
                    content=body,
                    workflow_type=workflow_type,
                    doc_type="handbook",
                    source_path=str(relative).replace("\\", "/"),
                )
            )
    return documents
