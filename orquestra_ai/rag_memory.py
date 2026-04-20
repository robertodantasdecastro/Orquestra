from __future__ import annotations

import json
import re
from typing import Any

from sqlmodel import Session, select

from rag.common import RagChunk, RagPaths
from rag.vectorstore import query_collection, upsert_chunks

from .config import OrquestraSettings
from .models import MemoryRecord

ORQUESTRA_MEMORY_COLLECTION = "orquestra_memory_v1"


def _safe_json(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_À-ÿ-]{3,}", text.lower())}


def _lexical_score(query: str, *parts: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    haystack_tokens = _tokens(" ".join(parts))
    if not haystack_tokens:
        return 0.0
    return len(query_tokens & haystack_tokens) / max(len(query_tokens), 1)


def _matches_metadata(
    metadata: dict[str, Any],
    *,
    project_id: str | None,
    session_id: str | None,
    scopes: list[str] | None,
    memory_kinds: list[str] | None,
    preset: str | None,
) -> bool:
    if project_id and metadata.get("project_id") not in (project_id, "", None):
        return False
    if session_id and metadata.get("session_id") not in (session_id, "", None):
        return False
    if scopes and metadata.get("scope") not in scopes:
        return False
    if memory_kinds and metadata.get("memory_kind") not in memory_kinds:
        return False
    if preset and metadata.get("preset") not in (preset, "", None):
        return False
    approved = metadata.get("approved", True)
    return approved in (True, "true", "True", 1, "1")


class RagMemoryService:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self.paths = RagPaths.load(settings.workspace_root)

    def upsert_memory(
        self,
        record: MemoryRecord,
        *,
        title: str | None = None,
        preset: str | None = None,
        source_kind: str = "memory_record",
        source_ref: str | None = None,
        approved: bool = True,
    ) -> dict[str, Any]:
        metadata = _safe_json(record.metadata_json, {})
        chunk = RagChunk(
            chunk_id=f"orquestra-memory:{record.id}",
            document_id=record.id,
            collection_name=ORQUESTRA_MEMORY_COLLECTION,
            text=record.content,
            metadata={
                "project_id": record.project_id or "",
                "session_id": record.session_id or "",
                "scope": record.scope,
                "memory_kind": record.memory_kind,
                "preset": preset or str(metadata.get("preset", "")),
                "source_kind": source_kind,
                "source_ref": source_ref or record.source,
                "approved": approved,
                "created_at": record.created_at.isoformat(),
                "title": title or str(metadata.get("title", record.source)),
            },
        )
        try:
            result = upsert_chunks(self.paths, ORQUESTRA_MEMORY_COLLECTION, [chunk])
            return {"ok": True, "backend": "chroma", **result}
        except Exception as exc:
            return {"ok": False, "backend": "fallback_only", "error": str(exc), "collection_name": ORQUESTRA_MEMORY_COLLECTION}

    def recall(
        self,
        query: str,
        *,
        session: Session | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        scopes: list[str] | None = None,
        memory_kinds: list[str] | None = None,
        preset: str | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        vector_error = ""
        try:
            hits = query_collection(self.paths, ORQUESTRA_MEMORY_COLLECTION, query, top_k=max(limit * 4, limit))
            for hit in hits:
                if not _matches_metadata(
                    hit.metadata,
                    project_id=project_id,
                    session_id=session_id,
                    scopes=scopes,
                    memory_kinds=memory_kinds,
                    preset=preset,
                ):
                    continue
                items.append(
                    {
                        "id": hit.chunk_id,
                        "title": hit.metadata.get("title") or hit.metadata.get("source_ref") or "memoria",
                        "content": hit.text,
                        "scope": hit.metadata.get("scope", "memory"),
                        "memory_kind": hit.metadata.get("memory_kind", "project"),
                        "source": hit.metadata.get("source_ref", ""),
                        "score": 1.0 - float(hit.distance or 0.0),
                        "metadata": hit.metadata | {"channel": "memory", "backend": "chroma"},
                    }
                )
                if len(items) >= limit:
                    break
        except Exception as exc:
            vector_error = str(exc)

        if len(items) < limit and session is not None:
            fallback_items = self._fallback_recall(
                session,
                query=query,
                project_id=project_id,
                session_id=session_id,
                scopes=scopes,
                memory_kinds=memory_kinds,
                preset=preset,
                limit=limit - len(items),
                excluded_ids={str(item["id"]).replace("orquestra-memory:", "") for item in items},
            )
            items.extend(fallback_items)

        return {
            "items": items[:limit],
            "collection_name": ORQUESTRA_MEMORY_COLLECTION,
            "status": "ok" if not vector_error else "fallback" if items else "unavailable",
            "error": vector_error,
        }

    def _fallback_recall(
        self,
        session: Session,
        *,
        query: str,
        project_id: str | None,
        session_id: str | None,
        scopes: list[str] | None,
        memory_kinds: list[str] | None,
        preset: str | None,
        limit: int,
        excluded_ids: set[str],
    ) -> list[dict[str, Any]]:
        statement = select(MemoryRecord).order_by(MemoryRecord.created_at.desc())
        if project_id:
            statement = statement.where((MemoryRecord.project_id == project_id) | (MemoryRecord.project_id.is_(None)))
        if session_id:
            statement = statement.where((MemoryRecord.session_id == session_id) | (MemoryRecord.session_id.is_(None)))
        if scopes:
            statement = statement.where(MemoryRecord.scope.in_(scopes))
        if memory_kinds:
            statement = statement.where(MemoryRecord.memory_kind.in_(memory_kinds))
        rows = session.exec(statement.limit(120)).all()
        ranked: list[dict[str, Any]] = []
        for record in rows:
            if record.id in excluded_ids:
                continue
            metadata = _safe_json(record.metadata_json, {})
            if preset and metadata.get("preset") not in (preset, "", None):
                continue
            score = _lexical_score(query, record.scope, record.source, record.content)
            if score <= 0:
                continue
            ranked.append(
                {
                    "id": record.id,
                    "title": metadata.get("title") or record.source,
                    "content": record.content,
                    "scope": record.scope,
                    "memory_kind": record.memory_kind,
                    "source": record.source,
                    "score": round(score, 4),
                    "metadata": metadata | {"channel": "memory", "backend": "lexical_fallback"},
                }
            )
        return sorted(ranked, key=lambda item: float(item["score"]), reverse=True)[:limit]

    @staticmethod
    def format_context(items: list[dict[str, Any]], *, max_chars: int = 4000) -> str:
        rendered: list[str] = []
        total = 0
        for item in items:
            line = (
                f"- [{item.get('scope', 'memory')}/{item.get('memory_kind', 'project')}] "
                f"{item.get('title', 'memoria')}: {item.get('content', '')}"
            ).strip()
            if total + len(line) > max_chars:
                break
            rendered.append(line)
            total += len(line)
        return "\n".join(rendered)
