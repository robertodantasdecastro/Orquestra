from __future__ import annotations

import json
import re
from typing import Any

from sqlmodel import Session, select

from .models import ChatSession, PlannerSnapshot, SessionSummary, SessionTask, utc_now
from .session_profile import get_session_profile


def _safe_json(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _bullet_lines(value: str, *, empty_fallback: list[str] | None = None) -> list[str]:
    lines = []
    for line in value.splitlines():
        normalized = line.strip().lstrip("- ").strip()
        if normalized:
            lines.append(normalized)
    return lines or list(empty_fallback or [])


def _normalize_subject(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _active_form(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if normalized.lower().startswith(("implementar", "validar", "revisar", "configurar", "criar", "documentar", "testar")):
        return normalized
    return f"Executar: {normalized}"


class PlannerService:
    def get_snapshot(self, session: Session, session_id: str) -> PlannerSnapshot | None:
        return session.exec(select(PlannerSnapshot).where(PlannerSnapshot.session_id == session_id)).first()

    def list_tasks(self, session: Session, session_id: str) -> list[SessionTask]:
        return session.exec(
            select(SessionTask).where(SessionTask.session_id == session_id).order_by(SessionTask.position, SessionTask.created_at)
        ).all()

    def rebuild_from_session(
        self,
        session: Session,
        *,
        chat_session: ChatSession,
        summary: SessionSummary,
    ) -> tuple[PlannerSnapshot, list[SessionTask]]:
        profile = get_session_profile(chat_session)
        sections = _safe_json(summary.sections_json, {})
        objective = str(profile.get("objective") or sections.get("objective") or chat_session.title)
        next_steps = _bullet_lines(
            str(sections.get("next_steps") or ""),
            empty_fallback=["Consolidar próximos passos a partir do objetivo da sessão."],
        )
        risks = _bullet_lines(str(sections.get("recent_failures") or sections.get("open_questions") or ""))
        strategy = str(sections.get("workflow") or sections.get("task_specification") or summary.current_state)

        snapshot = self.get_snapshot(session, chat_session.id)
        if snapshot is None:
            snapshot = PlannerSnapshot(
                session_id=chat_session.id,
                objective=objective,
                strategy=strategy,
                next_steps_json=json.dumps(next_steps, ensure_ascii=False),
                risks_json=json.dumps(risks, ensure_ascii=False),
                metadata_json=json.dumps({"source": "session_summary"}, ensure_ascii=False),
                last_planned_at=utc_now(),
            )
            session.add(snapshot)
            session.flush()
        else:
            snapshot.objective = objective
            snapshot.strategy = strategy
            snapshot.next_steps_json = json.dumps(next_steps, ensure_ascii=False)
            snapshot.risks_json = json.dumps(risks, ensure_ascii=False)
            snapshot.last_planned_at = utc_now()
            snapshot.updated_at = utc_now()
            snapshot.metadata_json = json.dumps(
                _safe_json(snapshot.metadata_json, {}) | {"source": "session_summary"},
                ensure_ascii=False,
            )
            session.add(snapshot)

        tasks = self.list_tasks(session, chat_session.id)
        task_map = {_normalize_subject(task.subject): task for task in tasks}
        for index, step in enumerate(next_steps[:8]):
            key = _normalize_subject(step)
            if not key:
                continue
            task = task_map.get(key)
            if task is None:
                task = SessionTask(
                    session_id=chat_session.id,
                    subject=step[:180],
                    description=step,
                    active_form=_active_form(step),
                    status="pending",
                    position=index,
                    metadata_json=json.dumps({"source": "planner_rebuild"}, ensure_ascii=False),
                )
                session.add(task)
                session.flush()
                task_map[key] = task
            else:
                task.description = step
                task.active_form = task.active_form or _active_form(step)
                task.position = index
                task.updated_at = utc_now()
                task.metadata_json = json.dumps(
                    _safe_json(task.metadata_json, {}) | {"source": "planner_rebuild"},
                    ensure_ascii=False,
                )
                session.add(task)

        return snapshot, self.list_tasks(session, chat_session.id)

    def create_task(
        self,
        session: Session,
        *,
        session_id: str,
        subject: str,
        description: str = "",
        active_form: str = "",
        status: str = "pending",
        owner: str = "orquestra",
        blocked_by: list[str] | None = None,
        blocks: list[str] | None = None,
        position: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionTask:
        tasks = self.list_tasks(session, session_id)
        normalized_subject = _normalize_subject(subject)
        for existing in tasks:
            if _normalize_subject(existing.subject) == normalized_subject:
                return existing
        task = SessionTask(
            session_id=session_id,
            subject=subject,
            description=description,
            active_form=active_form or _active_form(subject),
            status=status,
            owner=owner,
            blocked_by_json=json.dumps(blocked_by or [], ensure_ascii=False),
            blocks_json=json.dumps(blocks or [], ensure_ascii=False),
            position=position if position is not None else len(tasks),
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        session.add(task)
        session.flush()
        return task

    def update_task(
        self,
        session: Session,
        task: SessionTask,
        *,
        subject: str | None = None,
        description: str | None = None,
        active_form: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        blocked_by: list[str] | None = None,
        blocks: list[str] | None = None,
        position: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionTask:
        if subject is not None:
            task.subject = subject
        if description is not None:
            task.description = description
        if active_form is not None:
            task.active_form = active_form
        if status is not None:
            task.status = status
        if owner is not None:
            task.owner = owner
        if blocked_by is not None:
            task.blocked_by_json = json.dumps(blocked_by, ensure_ascii=False)
        if blocks is not None:
            task.blocks_json = json.dumps(blocks, ensure_ascii=False)
        if position is not None:
            task.position = position
        if metadata is not None:
            task.metadata_json = json.dumps(_safe_json(task.metadata_json, {}) | metadata, ensure_ascii=False)
        task.updated_at = utc_now()
        session.add(task)
        session.flush()
        return task

    def task_prompt_context(self, session: Session, session_id: str, *, limit: int = 6) -> str:
        tasks = [
            task
            for task in self.list_tasks(session, session_id)
            if task.status not in {"completed", "cancelled"}
        ][:limit]
        if not tasks:
            return ""
        return "\n".join(
            f"- [{task.status}] {task.subject}: {task.active_form or task.description or task.subject}"
            for task in tasks
        )
