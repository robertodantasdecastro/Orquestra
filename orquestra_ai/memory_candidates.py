from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from .memory_types import default_memory_kind_for_preset
from .models import ChatMessage, ChatSession, MemoryReviewCandidate


PRESET_SCOPE = {
    "research": "source_fact",
    "osint": "source_fact",
    "persona": "persona_memory",
    "assistant": "session_memory",
    "dataset": "training_signal",
}


def _truncate(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 1, 1)].rstrip() + "..."


def _loads(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


class MemoryCandidateExtractor:
    def extract_from_chat_turn(
        self,
        session: Session,
        *,
        chat_session: ChatSession,
        profile: dict[str, Any],
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        citations: list[dict[str, Any]] | None = None,
        recalled: list[dict[str, Any]] | None = None,
    ) -> list[MemoryReviewCandidate]:
        memory_policy = profile.get("memory_policy", {})
        if memory_policy.get("enabled") is False or memory_policy.get("auto_capture") is False:
            return []

        interaction_key = f"{user_message.id}:{assistant_message.id}"
        existing = session.exec(
            select(MemoryReviewCandidate)
            .where(MemoryReviewCandidate.session_id == chat_session.id)
            .where(MemoryReviewCandidate.status == "pending")
        ).all()
        for candidate in existing:
            metadata = _loads(candidate.metadata_json, {})
            if metadata.get("interaction_key") == interaction_key:
                return []

        preset = str(profile.get("preset") or "assistant")
        scope = PRESET_SCOPE.get(preset, "session_memory")
        memory_kind = default_memory_kind_for_preset(preset)
        objective = str(profile.get("objective") or "")
        title_seed = _truncate(user_message.content, 64) or "Interacao de chat"
        source_ids = [user_message.id, assistant_message.id]
        content = "\n\n".join(
            [
                f"Objetivo da sessao: {objective or 'nao definido'}",
                f"Pergunta: {user_message.content.strip()}",
                f"Resposta: {assistant_message.content.strip()}",
            ]
        )
        candidate = MemoryReviewCandidate(
            project_id=chat_session.project_id,
            session_id=chat_session.id,
            scope=scope,
            memory_kind=memory_kind,
            title=f"{preset}: {title_seed}",
            content=content,
            rationale=(
                "Captura automatica revisavel para reforcar continuidade de contexto, "
                "recall RAG e possivel curadoria futura."
            ),
            source_message_ids_json=json.dumps(source_ids, ensure_ascii=False),
            citations_json=json.dumps(citations or [], ensure_ascii=False),
            confidence=0.68 if recalled else 0.58,
            status="pending",
            metadata_json=json.dumps(
                {
                    "preset": preset,
                    "memory_kind": memory_kind,
                    "objective": objective,
                    "interaction_key": interaction_key,
                    "review_required": True,
                    "training_candidate_requested": bool(memory_policy.get("generate_training_candidates")),
                    "rag_recall_count": len(recalled or []),
                },
                ensure_ascii=False,
            ),
        )
        session.add(candidate)
        session.flush()
        return [candidate]
