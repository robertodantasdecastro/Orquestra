from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from rag.common import append_jsonl, read_jsonl, write_json

from .config import OrquestraSettings
from .models import (
    ChatMessage,
    ChatSession,
    MemoryManifestEntry,
    MemoryRecord,
    MemoryTopic,
    SessionSummary,
    SessionTranscript,
    TrainingCandidate,
    utc_now,
)
from .vector_index import OrquestraVectorIndex, blend_scores, recency_bonus, score_overlap


SECTION_ORDER = [
    "current_state",
    "task_specification",
    "files_and_functions",
    "workflow",
    "errors_and_corrections",
    "key_results",
    "worklog",
]


@dataclass
class MemoryGraphPaths:
    root: Path
    transcripts_dir: Path
    summaries_dir: Path
    topics_dir: Path
    manifests_dir: Path
    training_dir: Path

    @classmethod
    def from_settings(cls, settings: OrquestraSettings) -> "MemoryGraphPaths":
        root = settings.artifacts_root / "memorygraph"
        return cls(
            root=root,
            transcripts_dir=root / "transcripts",
            summaries_dir=root / "session_summaries",
            topics_dir=root / "topics",
            manifests_dir=root / "manifests",
            training_dir=root / "training_candidates",
        )

    def ensure(self) -> None:
        for path in (
            self.root,
            self.transcripts_dir,
            self.summaries_dir,
            self.topics_dir,
            self.manifests_dir,
            self.training_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def _slugify(raw: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return normalized or "item"


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _truncate(text: str, size: int) -> str:
    text = text.strip()
    if len(text) <= size:
        return text
    return text[: max(size - 1, 1)].rstrip() + "…"


def _extract_code_tokens(text: str) -> list[str]:
    matches = re.findall(r"`([^`]+)`|([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+)|([A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+)", text)
    results: list[str] = []
    for group in matches:
        for item in group:
            if item and item not in results:
                results.append(item)
    return results[:12]


class MemoryGraphService:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self.paths = MemoryGraphPaths.from_settings(settings)
        self.paths.ensure()
        self.index = OrquestraVectorIndex(settings)

    def transcript_path(self, session_id: str) -> Path:
        return self.paths.transcripts_dir / f"{_slugify(session_id)}.jsonl"

    def summary_path(self, session_id: str) -> Path:
        return self.paths.summaries_dir / f"{_slugify(session_id)}.md"

    def topic_path(self, slug: str) -> Path:
        return self.paths.topics_dir / f"{slug}.md"

    def manifest_path(self, slug: str) -> Path:
        return self.paths.manifests_dir / f"{slug}.json"

    def candidate_path(self, candidate_id: str) -> Path:
        return self.paths.training_dir / f"{_slugify(candidate_id)}.json"

    def append_transcript_message(
        self,
        session: Session,
        chat_session: ChatSession,
        message: ChatMessage,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> SessionTranscript:
        transcript_path = self.transcript_path(chat_session.id)
        payload = {
            "message_id": message.id,
            "session_id": chat_session.id,
            "role": message.role,
            "content": message.content,
            "provider_id": message.provider_id,
            "model_name": message.model_name,
            "usage": json.loads(message.usage_json or "{}"),
            "latency_seconds": message.latency_seconds,
            "metadata": metadata or json.loads(message.metadata_json or "{}"),
            "created_at": message.created_at.isoformat(),
        }
        append_jsonl(transcript_path, payload)
        transcript = session.exec(select(SessionTranscript).where(SessionTranscript.session_id == chat_session.id)).first()
        size_bytes = transcript_path.stat().st_size if transcript_path.exists() else 0
        if transcript is None:
            transcript = SessionTranscript(
                session_id=chat_session.id,
                storage_path=str(transcript_path),
                message_count=1,
                transcript_bytes=size_bytes,
                last_message_id=message.id,
            )
            session.add(transcript)
        else:
            transcript.message_count += 1
            transcript.transcript_bytes = size_bytes
            transcript.last_message_id = message.id
            transcript.updated_at = utc_now()
        return transcript

    def list_transcript_messages(self, session_id: str) -> list[dict[str, Any]]:
        return read_jsonl(self.transcript_path(session_id))

    def build_session_summary(self, session: Session, chat_session: ChatSession) -> SessionSummary:
        rows = session.exec(select(ChatMessage).where(ChatMessage.session_id == chat_session.id).order_by(ChatMessage.created_at)).all()
        sections = self._build_summary_sections(chat_session, rows)
        markdown = self._render_summary_markdown(chat_session, sections)
        summary_path = self.summary_path(chat_session.id)
        summary_path.write_text(markdown, encoding="utf-8")
        summary = session.exec(select(SessionSummary).where(SessionSummary.session_id == chat_session.id)).first()
        last_message_id = rows[-1].id if rows else None
        if summary is None:
            summary = SessionSummary(
                session_id=chat_session.id,
                summary_path=str(summary_path),
                current_state=sections["current_state"],
                sections_json=json.dumps(sections, ensure_ascii=False),
                last_message_id=last_message_id,
            )
            session.add(summary)
        else:
            summary.summary_path = str(summary_path)
            summary.current_state = sections["current_state"]
            summary.sections_json = json.dumps(sections, ensure_ascii=False)
            summary.last_message_id = last_message_id
            summary.updated_at = utc_now()
        return summary

    def get_or_build_summary(self, session: Session, chat_session: ChatSession) -> SessionSummary:
        summary = session.exec(select(SessionSummary).where(SessionSummary.session_id == chat_session.id)).first()
        if summary is None:
            return self.build_session_summary(session, chat_session)
        return summary

    def recall_memories(
        self,
        session: Session,
        *,
        query: str,
        project_id: str | None = None,
        scopes: list[str] | None = None,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        records_statement = select(MemoryRecord).order_by(MemoryRecord.created_at.desc())
        topics_statement = select(MemoryTopic).order_by(MemoryTopic.updated_at.desc())
        if project_id:
            records_statement = records_statement.where((MemoryRecord.project_id == project_id) | (MemoryRecord.project_id.is_(None)))
            topics_statement = topics_statement.where((MemoryTopic.project_id == project_id) | (MemoryTopic.project_id.is_(None)))
        if scopes:
            records_statement = records_statement.where(MemoryRecord.scope.in_(scopes))
            topics_statement = topics_statement.where(MemoryTopic.scope.in_(scopes))

        records = session.exec(records_statement.limit(80)).all()
        topics = session.exec(topics_statement.limit(40)).all()
        now = _as_utc(utc_now())

        candidates: list[dict[str, Any]] = []
        for record in records:
            score = score_overlap(query, record.scope, record.source, record.content)
            score = blend_scores(score, recency_bonus((now - _as_utc(record.created_at)).total_seconds() / 3600))
            if score <= 0:
                continue
            candidates.append(
                {
                    "kind": "memory_record",
                    "id": record.id,
                    "scope": record.scope,
                    "title": record.source,
                    "content": record.content,
                    "score": score,
                    "metadata": json.loads(record.metadata_json or "{}"),
                    "created_at": record.created_at.isoformat(),
                }
            )

        for topic in topics:
            score = score_overlap(query, topic.title, topic.description, topic.scope)
            score = blend_scores(score, recency_bonus((now - _as_utc(topic.updated_at)).total_seconds() / 3600))
            if score <= 0:
                continue
            topic_text = self.topic_path(topic.slug).read_text(encoding="utf-8", errors="ignore") if self.topic_path(topic.slug).exists() else ""
            candidates.append(
                {
                    "kind": "memory_topic",
                    "id": topic.id,
                    "scope": topic.scope,
                    "title": topic.title,
                    "content": _truncate(topic_text, 1200),
                    "score": score,
                    "metadata": json.loads(topic.metadata_json or "{}"),
                    "created_at": topic.updated_at.isoformat(),
                }
            )

        semantic_hits = self.index.query("memory_graph", query, limit=limit)
        semantic_map = {hit.point_id: hit.score for hit in semantic_hits}
        for item in candidates:
            item["score"] = round(item["score"] + semantic_map.get(item["id"], 0.0), 4)

        ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
        return ranked[:limit]

    def promote_to_topic(
        self,
        session: Session,
        *,
        project_id: str | None,
        scope: str,
        title: str,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[MemoryTopic, MemoryManifestEntry, MemoryRecord]:
        slug = _slugify(f"{scope}-{title}-{project_id or 'global'}")
        topic_path = self.topic_path(slug)
        manifest_path = self.manifest_path(slug)
        payload_metadata = metadata or {}
        markdown = "\n".join(
            [
                "---",
                f"title: {title}",
                f"scope: {scope}",
                f"project_id: {project_id or ''}",
                f"source: {source}",
                f"updated_at: {utc_now().isoformat()}",
                "---",
                "",
                f"# {title}",
                "",
                content.strip(),
                "",
            ]
        )
        topic_path.write_text(markdown, encoding="utf-8")

        topic = session.exec(select(MemoryTopic).where(MemoryTopic.slug == slug)).first()
        if topic is None:
            topic = MemoryTopic(
                project_id=project_id,
                scope=scope,
                slug=slug,
                title=title,
                description=_truncate(content, 220),
                topic_path=str(topic_path),
                manifest_path=str(manifest_path),
                metadata_json=json.dumps(payload_metadata, ensure_ascii=False),
            )
            session.add(topic)
            session.flush()
        else:
            topic.title = title
            topic.description = _truncate(content, 220)
            topic.topic_path = str(topic_path)
            topic.manifest_path = str(manifest_path)
            topic.metadata_json = json.dumps(payload_metadata, ensure_ascii=False)
            topic.last_used_at = utc_now()
            topic.updated_at = utc_now()

        entry = MemoryManifestEntry(
            topic_id=topic.id,
            entry_kind="summary",
            label=title,
            summary=_truncate(content, 320),
            source_ref=source,
            relevance=0.7,
            metadata_json=json.dumps(payload_metadata, ensure_ascii=False),
        )
        session.add(entry)

        record = MemoryRecord(
            project_id=project_id,
            topic_id=topic.id,
            scope=scope,
            source=source,
            content=content.strip(),
            confidence=0.78,
            metadata_json=json.dumps(payload_metadata, ensure_ascii=False),
        )
        session.add(record)

        manifest_payload = {
            "topic_id": topic.id,
            "scope": scope,
            "title": title,
            "description": topic.description,
            "source_ref": source,
            "updated_at": utc_now().isoformat(),
            "metadata": payload_metadata,
        }
        write_json(manifest_path, manifest_payload)
        self.index.upsert(
            "memory_graph",
            [
                {
                    "id": topic.id,
                    "text": f"{title}\n{content}",
                    "payload": {
                        "original_id": topic.id,
                        "kind": "memory_topic",
                        "scope": scope,
                        "title": title,
                        "project_id": project_id or "",
                        "source_ref": source,
                    },
                },
                {
                    "id": record.id,
                    "text": content,
                    "payload": {
                        "original_id": record.id,
                        "kind": "memory_record",
                        "scope": scope,
                        "title": title,
                        "project_id": project_id or "",
                        "source_ref": source,
                    },
                },
            ],
        )
        return topic, entry, record

    def create_training_candidate(
        self,
        session: Session,
        *,
        project_id: str | None,
        session_id: str | None,
        source: str,
        instruction: str,
        context: str,
        response: str,
        labels: dict[str, Any] | None = None,
        approved: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> TrainingCandidate:
        candidate = TrainingCandidate(
            project_id=project_id,
            session_id=session_id,
            source=source,
            instruction=instruction,
            context=context,
            response=response,
            labels_json=json.dumps(labels or {}, ensure_ascii=False),
            approved=approved,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        session.add(candidate)
        session.flush()
        write_json(
            self.candidate_path(candidate.id),
            {
                "id": candidate.id,
                "project_id": project_id,
                "session_id": session_id,
                "source": source,
                "instruction": instruction,
                "context": context,
                "response": response,
                "labels": labels or {},
                "approved": approved,
                "metadata": metadata or {},
                "created_at": candidate.created_at.isoformat(),
            },
        )
        return candidate

    def build_resume_payload(self, session: Session, chat_session: ChatSession) -> dict[str, Any]:
        summary = self.get_or_build_summary(session, chat_session)
        transcript = session.exec(select(SessionTranscript).where(SessionTranscript.session_id == chat_session.id)).first()
        messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == chat_session.id).order_by(ChatMessage.created_at.desc())).all()
        return {
            "session_id": chat_session.id,
            "title": chat_session.title,
            "provider_id": chat_session.provider_id,
            "model_name": chat_session.model_name,
            "status": chat_session.status,
            "summary": {
                "current_state": summary.current_state,
                "sections": json.loads(summary.sections_json or "{}"),
                "updated_at": summary.updated_at.isoformat(),
                "summary_path": summary.summary_path,
            },
            "transcript": {
                "storage_path": transcript.storage_path if transcript else str(self.transcript_path(chat_session.id)),
                "message_count": transcript.message_count if transcript else 0,
                "transcript_bytes": transcript.transcript_bytes if transcript else 0,
            },
            "recent_messages": [
                {
                    "id": item.id,
                    "role": item.role,
                    "content": item.content,
                    "provider_id": item.provider_id,
                    "model_name": item.model_name,
                    "created_at": item.created_at.isoformat(),
                }
                for item in reversed(messages[:12])
            ],
        }

    def compact_session(self, session: Session, chat_session: ChatSession) -> dict[str, Any]:
        summary = self.build_session_summary(session, chat_session)
        transcript_entries = self.list_transcript_messages(chat_session.id)
        kept = transcript_entries[-80:]
        compacted_path = self.transcript_path(chat_session.id)
        compacted_path.write_text("", encoding="utf-8")
        for item in kept:
            append_jsonl(compacted_path, item)
        transcript = session.exec(select(SessionTranscript).where(SessionTranscript.session_id == chat_session.id)).first()
        if transcript is not None:
            transcript.message_count = len(kept)
            transcript.transcript_bytes = compacted_path.stat().st_size if compacted_path.exists() else 0
            transcript.updated_at = utc_now()
        return {
            "session_id": chat_session.id,
            "summary_path": summary.summary_path,
            "kept_messages": len(kept),
            "transcript_path": str(compacted_path),
        }

    def _build_summary_sections(self, chat_session: ChatSession, rows: list[ChatMessage]) -> dict[str, str]:
        first_user = next((row.content for row in rows if row.role == "user"), "")
        last_user = next((row.content for row in reversed(rows) if row.role == "user"), "")
        last_assistant = next((row.content for row in reversed(rows) if row.role == "assistant"), "")
        snippets = []
        commands = []
        errors = []
        worklog = []
        for row in rows[-20:]:
            snippet_tokens = _extract_code_tokens(row.content)
            if snippet_tokens:
                snippets.extend(token for token in snippet_tokens if token not in snippets)
            for line in row.content.splitlines():
                stripped = line.strip()
                if stripped.startswith("$ ") or stripped.startswith("> "):
                    commands.append(stripped)
                lowered = stripped.lower()
                if any(term in lowered for term in ("erro", "falha", "failed", "exception", "traceback")):
                    errors.append(stripped)
            worklog.append(f"- {row.role}: {_truncate(row.content, 120)}")

        current_state = _truncate(last_user or last_assistant or chat_session.title, 240)
        return {
            "current_state": current_state,
            "task_specification": _truncate(first_user or chat_session.title, 420),
            "files_and_functions": "\n".join(f"- {item}" for item in snippets[:12]) or "- Nenhum arquivo destacado ainda.",
            "workflow": "\n".join(f"- {item}" for item in commands[:10]) or "- Fluxo ainda sem comandos recorrentes.",
            "errors_and_corrections": "\n".join(f"- {item}" for item in errors[:8]) or "- Sem erros relevantes registrados.",
            "key_results": _truncate(last_assistant or "Sem resposta consolidada ainda.", 600),
            "worklog": "\n".join(worklog[-12:]) or "- Sessão recém-criada.",
        }

    def _render_summary_markdown(self, chat_session: ChatSession, sections: dict[str, str]) -> str:
        labels = {
            "current_state": "Current State",
            "task_specification": "Task Specification",
            "files_and_functions": "Files and Functions",
            "workflow": "Workflow",
            "errors_and_corrections": "Errors & Corrections",
            "key_results": "Key Results",
            "worklog": "Worklog",
        }
        lines = [
            f"# Session Title\n{chat_session.title}",
            "",
        ]
        for key in SECTION_ORDER:
            lines.extend([f"# {labels[key]}", sections.get(key, ""), ""])
        return "\n".join(lines).strip() + "\n"
