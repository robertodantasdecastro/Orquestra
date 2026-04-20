from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from .config import OrquestraSettings
from .memory_graph import MemoryGraphService
from .models import MemoryRecord
from .rag_memory import RagMemoryService

VALID_SELECTOR_MODES = {"hybrid", "lexical"}


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


def _safe_json(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def normalize_selector_mode(raw_mode: str | None) -> str:
    normalized = (raw_mode or "hybrid").strip().lower()
    return normalized if normalized in VALID_SELECTOR_MODES else "hybrid"


class MemoryRecallService:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self.memory_graph = MemoryGraphService(settings)
        self.rag_memory = RagMemoryService(settings)

    def recall(
        self,
        session: Session,
        *,
        query: str,
        project_id: str | None = None,
        session_id: str | None = None,
        scopes: list[str] | None = None,
        memory_kinds: list[str] | None = None,
        preset: str | None = None,
        limit: int = 6,
        selector_mode: str = "hybrid",
    ) -> dict[str, Any]:
        normalized_selector = normalize_selector_mode(selector_mode)
        lexical = self._lexical_shortlist(
            session,
            query=query,
            project_id=project_id,
            session_id=session_id,
            scopes=scopes,
            memory_kinds=memory_kinds,
            limit=max(limit * 2, limit),
        )
        lexical = [
            item | {"metadata": item.get("metadata", {}) | {"selector_mode": normalized_selector}}
            for item in lexical
        ]
        if normalized_selector == "lexical":
            return {
                "items": lexical[:limit],
                "status": "ok",
                "selector_mode": normalized_selector,
                "vector_status": "skipped",
                "vector_error": None,
                "collection_name": "orquestra_memory_v1",
            }

        vector = self.rag_memory.recall(
            query,
            session=session,
            project_id=project_id,
            session_id=session_id,
            scopes=scopes,
            memory_kinds=memory_kinds,
            preset=preset,
            limit=max(limit * 2, limit),
        )

        combined: dict[str, dict[str, Any]] = {}
        for item in lexical:
            combined[item["id"]] = item | {"score": round(float(item.get("score", 0.0)), 4)}

        for item in vector.get("items", []):
            normalized_id = str(item["id"]).replace("orquestra-memory:", "")
            current = combined.get(normalized_id)
            score = round(float(item.get("score", 0.0)) * 1.2 + float(current.get("score", 0.0) if current else 0.0), 4)
            merged_metadata = (current.get("metadata", {}) if current else {}) | item.get("metadata", {})
            combined[normalized_id] = {
                "id": normalized_id,
                "title": item.get("title") or (current.get("title") if current else "memoria"),
                "content": item.get("content") or (current.get("content") if current else ""),
                "scope": item.get("scope") or (current.get("scope") if current else "memory"),
                "memory_kind": item.get("memory_kind") or (current.get("memory_kind") if current else "project"),
                "source": item.get("source") or (current.get("source") if current else ""),
                "score": score,
                "metadata": merged_metadata | {"selector_mode": normalized_selector},
            }

        items = sorted(combined.values(), key=lambda row: float(row.get("score", 0.0)), reverse=True)[:limit]
        return {
            "items": items,
            "status": "ok" if vector.get("status") == "ok" else "hybrid_fallback",
            "selector_mode": normalized_selector,
            "vector_status": vector.get("status"),
            "vector_error": vector.get("error"),
            "collection_name": vector.get("collection_name"),
        }

    def format_context(self, items: list[dict[str, Any]], *, max_chars: int = 4000) -> str:
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

    def _lexical_shortlist(
        self,
        session: Session,
        *,
        query: str,
        project_id: str | None,
        session_id: str | None,
        scopes: list[str] | None,
        memory_kinds: list[str] | None,
        limit: int,
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

        rows = session.exec(statement.limit(160)).all()
        ranked: list[dict[str, Any]] = []
        for record in rows:
            metadata = _safe_json(record.metadata_json, {})
            score = _lexical_score(query, record.memory_kind, record.scope, record.source, record.content)
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
                    "metadata": metadata | {"backend": "sqlite_lexical", "channel": "memory"},
                }
            )

        seen = {item["id"] for item in ranked}
        for header in self.memory_graph.scan_projected_memory_headers(
            session,
            project_id=project_id,
            session_id=session_id,
            scopes=scopes,
            memory_kinds=memory_kinds,
        ):
            score = _lexical_score(query, header["title"], header["scope"], header["memory_kind"], Path(header["path"]).name)
            if score <= 0:
                continue
            if header["id"] in seen:
                for item in ranked:
                    if item["id"] == header["id"]:
                        item["score"] = round(float(item["score"]) + score * 0.4, 4)
                        item["metadata"] = item.get("metadata", {}) | {
                            "projection_path": header["path"],
                            "projection_title": header["title"],
                        }
                        break
                continue
            ranked.append(
                {
                    "id": header["id"],
                    "title": header["title"],
                    "content": f"Memória projetada em {Path(header['path']).name}",
                    "scope": header["scope"],
                    "memory_kind": header["memory_kind"],
                    "source": header["path"],
                    "score": round(score * 0.8, 4),
                    "metadata": {"backend": "memdir_headers", "channel": "memory", "projection_path": header["path"]},
                }
            )

        return sorted(ranked, key=lambda row: float(row["score"]), reverse=True)[:limit]
