"""JSONL long-term memory of compact workflow outcomes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.memory.contracts import MemoryRecord
from app.memory.safety import sanitize_long_term_payload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = PROJECT_ROOT / "data" / "memory" / "long_term.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LongTermMemory:
    """Persistent compact facts, scoped by employee_id and workflow_type."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_PATH
        self._records: list[MemoryRecord] = []
        self._load()

    def reset(self) -> None:
        self._records = []
        if self._path.exists():
            self._path.unlink()

    def _load(self) -> None:
        self._records = []
        if not self._path.exists():
            return
        with self._path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                self._records.append(MemoryRecord.model_validate(json.loads(line)))

    def _append_file(self, record: MemoryRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    def write(self, payload: dict) -> MemoryRecord:
        cleaned = sanitize_long_term_payload(payload)
        timestamp = str(cleaned.get("timestamp") or _utc_now())
        record = MemoryRecord(
            memory_id=str(uuid.uuid4()),
            layer="long_term",
            kind="outcome",
            workflow_id=cleaned.get("workflow_id"),
            employee_id=cleaned.get("employee_id"),
            workflow_type=cleaned.get("workflow_type"),
            content=str(cleaned.get("rationale_summary") or ""),
            metadata=cleaned,
            timestamp=timestamp,
        )
        self._records.append(record)
        self._append_file(record)
        return record

    def query(
        self,
        *,
        employee_id: str,
        workflow_type: str | None = None,
    ) -> list[MemoryRecord]:
        target = employee_id.strip().upper()
        results: list[MemoryRecord] = []
        for record in self._records:
            if str(record.employee_id or "").upper() != target:
                continue
            if workflow_type and record.workflow_type != workflow_type:
                continue
            results.append(record)
        return results


_STORE: LongTermMemory | None = None


def get_long_term_store() -> LongTermMemory:
    global _STORE
    if _STORE is None:
        _STORE = LongTermMemory()
    return _STORE


def reset_long_term() -> LongTermMemory:
    store = get_long_term_store()
    store.reset()
    return store
