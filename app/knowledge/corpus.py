"""Load curated knowledge documents from data/knowledge.

Layout (extensible for multi-company SaaS):

  data/knowledge/
    global/                          # system-wide knowledge
    leave/                           # workflow domain knowledge (global scope)
    recruitment/
    onboarding/
    performance/
    offboarding/
    organizations/
      {organization_id}/
        leave/
        ...

Organization-specific documents never leak across tenants. File-upload UI and
cloud storage are intentionally not implemented here.
"""

from __future__ import annotations

from pathlib import Path

from app.knowledge.contracts import KnowledgeDocument

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"

WORKFLOW_TYPE_BY_FOLDER = {
    "global": "general",
    "leave": "leave_attendance",
    "recruitment": "recruitment",
    "onboarding": "onboarding",
    "performance": "performance",
    "offboarding": "offboarding",
    "attendance": "attendance",
    "training": "training",
    "hr_services": "hr_services",
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


def _documents_from_path(
    path: Path,
    *,
    organization_id: str,
    workflow_type: str,
    doc_type: str = "handbook",
) -> list[KnowledgeDocument]:
    relative = path.relative_to(KNOWLEDGE_DIR)
    text = path.read_text(encoding="utf-8")
    documents: list[KnowledgeDocument] = []
    for index, (title, body) in enumerate(_split_markdown(text), start=1):
        org_prefix = organization_id or "global"
        documents.append(
            KnowledgeDocument(
                document_id=f"{org_prefix}-{path.stem}-{index}",
                title=title,
                content=body,
                workflow_type=workflow_type,
                doc_type=doc_type,
                source_path=str(relative).replace("\\", "/"),
                organization_id=organization_id,
            )
        )
    return documents


def _workflow_type_for_path(root: Path, path: Path, *, domain_hint: str | None) -> str:
    """Map a markdown path to workflow_type using domain folder names."""

    relative = path.relative_to(root)
    if domain_hint:
        # Domain root such as data/knowledge/leave/ or organizations/acme/leave/
        if domain_hint == "global" and len(relative.parts) == 1:
            return "general"
        return WORKFLOW_TYPE_BY_FOLDER.get(domain_hint, domain_hint)

    # Organization root: first path segment is the domain folder
    folder = relative.parts[0] if relative.parts else "general"
    if folder.endswith(".md"):
        return "general"
    return WORKFLOW_TYPE_BY_FOLDER.get(folder, folder)


def _load_domain_tree(
    root: Path,
    *,
    organization_id: str,
    domain_hint: str | None = None,
) -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []
    if not root.exists():
        return documents
    for path in sorted(root.rglob("*.md")):
        workflow_type = _workflow_type_for_path(root, path, domain_hint=domain_hint)
        documents.extend(
            _documents_from_path(
                path,
                organization_id=organization_id,
                workflow_type=workflow_type,
            )
        )
    return documents


def load_knowledge_documents() -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []
    if not KNOWLEDGE_DIR.exists():
        return documents

    # Global / domain folders at the knowledge root (existing leave handbook stays here).
    for entry in sorted(KNOWLEDGE_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name == "organizations":
            continue
        documents.extend(
            _load_domain_tree(
                entry,
                organization_id="",
                domain_hint=entry.name,
            )
        )

    # Future company-specific knowledge: organizations/{organization_id}/...
    org_root = KNOWLEDGE_DIR / "organizations"
    if org_root.exists():
        for org_dir in sorted(org_root.iterdir()):
            if not org_dir.is_dir():
                continue
            documents.extend(
                _load_domain_tree(
                    org_dir,
                    organization_id=org_dir.name,
                    domain_hint=None,
                )
            )

    return documents
