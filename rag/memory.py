from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import RagPaths, append_jsonl, read_jsonl, sanitize_metadata, utc_now, write_json
from .vectorstore import query_collection, upsert_chunks
from .common import RagChunk, slugify


class MemoryManager:
    def __init__(self, paths: RagPaths) -> None:
        self.paths = paths
        self.paths.ensure()

    def _session_file(self, session_id: str) -> Path:
        return self.paths.session_memory_dir / f"{slugify(session_id)}.jsonl"

    def _episodic_file(self, session_id: str) -> Path:
        return self.paths.episodic_memory_dir / f"{slugify(session_id)}.jsonl"

    def recent_history(self, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
        return read_jsonl(self._session_file(session_id))[-limit:]

    def episodic_facts(self, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
        return read_jsonl(self._episodic_file(session_id))[-limit:]

    def build_memory_context(self, session_id: str, *, history_limit: int = 6, fact_limit: int = 6) -> str:
        history = self.recent_history(session_id, limit=history_limit)
        facts = self.episodic_facts(session_id, limit=fact_limit)
        lines: list[str] = []
        if facts:
            lines.append("Fatos de memoria de longo prazo:")
            for item in facts:
                lines.append(f"- {item.get('fact', '')}")
        if history:
            lines.append("Historico recente:")
            for item in history:
                lines.append(f"Q: {item.get('question', '')}")
                lines.append(f"A: {item.get('answer', '')}")
        return "\n".join(lines).strip()

    def record_interaction(self, session_id: str, payload: dict[str, Any]) -> None:
        append_jsonl(self._session_file(session_id), payload)

    def promote_fact(self, session_id: str, fact: str, *, source: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "session_id": session_id,
            "fact": fact.strip(),
            "source": source,
            "created_at": utc_now(),
            "metadata": sanitize_metadata(metadata or {}),
        }
        append_jsonl(self._episodic_file(session_id), payload)
        chunk = RagChunk(
            chunk_id=f"{slugify(session_id)}:{slugify(source)}:{slugify(utc_now())}",
            document_id=slugify(session_id),
            collection_name="memory_facts",
            text=fact.strip(),
            metadata={"session_id": session_id, "source": source, **(metadata or {})},
        )
        upsert_chunks(self.paths, "memory_facts", [chunk])
        return payload

    def retrieve_memory_facts(self, query_text: str, *, top_k: int = 3) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": item.chunk_id,
                "text": item.text,
                "metadata": item.metadata,
                "distance": item.distance,
            }
            for item in query_collection(self.paths, "memory_facts", query_text, top_k=top_k)
        ]

    def snapshot(self) -> dict[str, Any]:
        sessions = sorted(self.paths.session_memory_dir.glob("*.jsonl"))
        episodic = sorted(self.paths.episodic_memory_dir.glob("*.jsonl"))
        payload = {
            "sessions": len(sessions),
            "episodic_files": len(episodic),
            "latest_session": sessions[-1].name if sessions else None,
            "latest_fact_file": episodic[-1].name if episodic else None,
            "updated_at": utc_now(),
        }
        write_json(self.paths.memory_root / "snapshot.json", payload)
        return payload
