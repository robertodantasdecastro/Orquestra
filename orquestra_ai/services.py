from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from rag.common import RagPaths
from rag.graph import RagWorkflow
from rag.vectorstore import query_collection

from .config import OrquestraSettings
from .gateway import GatewayProvider
from .memory_graph import MemoryGraphService
from .memory_recall import MemoryRecallService, normalize_selector_mode
from .models import (
    JobRecord,
    MemoryManifestEntry,
    MemoryRecord,
    MemoryReviewCandidate,
    MemoryTopic,
    ModelArtifact,
    PlannerSnapshot,
    Project,
    ProjectDeployment,
    ProviderProfile,
    SessionCompactionState,
    SessionSummary,
    SessionTask,
    SessionTranscript,
    TrainingCandidate,
    WorkflowRun,
    WorkflowStepRun,
    WorkspaceAsset,
    WorkspaceDerivative,
    WorkspaceInsight,
    WorkspaceScan,
)
from .osint import OsintService
from .planner import PlannerService
from .rag_memory import RagMemoryService
from .runtime_state import runtime_backup_dir, runtime_install_dir
from .session_profile import get_session_profile, profile_prompt_section
from .workspace import WorkspaceService

DEFAULT_SOURCE_COLLECTIONS = ("knowledge_base", "security_base")


def seed_default_state(session: Session, settings: OrquestraSettings) -> None:
    seed_default_providers(session, settings)
    seed_default_project(session, settings)


def seed_default_project(session: Session, settings: OrquestraSettings) -> None:
    existing = session.exec(select(Project).where(Project.slug == settings.default_project_slug)).first()
    if existing:
        if (
            existing.name == "Local RAG Lab"
            and existing.description == "Projeto padrao do control plane Orquestra AI."
        ):
            existing.name = "Orquestra Lab"
            existing.description = "Projeto padrao do workspace Orquestra AI."
            session.add(existing)
            session.commit()
        return
    session.add(
        Project(
            slug=settings.default_project_slug,
            name="Orquestra Lab",
            description="Projeto padrao do workspace Orquestra AI.",
            default_provider_id=settings.default_provider_id,
            default_model=settings.local_chat_model,
        )
    )
    session.commit()


def seed_default_providers(session: Session, settings: OrquestraSettings) -> None:
    defaults = [
        {
            "provider_id": "lmstudio",
            "label": "LM Studio Local",
            "transport": "openai_compatible",
            "base_url": settings.litellm_proxy_url or "http://localhost:1234/v1",
            "api_key_env": "LMSTUDIO_API_KEY",
            "default_model": settings.local_chat_model,
            "model_prefix": "openai",
            "capabilities": ["chat", "streaming", "structured_output", "vision", "embeddings", "local_only"],
            "config": {"mode": "gui_or_headless"},
        },
        {
            "provider_id": "openai",
            "label": "OpenAI",
            "transport": "litellm",
            "base_url": settings.litellm_proxy_url,
            "api_key_env": "OPENAI_API_KEY",
            "default_model": os_env("ORQUESTRA_OPENAI_MODEL", "gpt-4.1-mini"),
            "model_prefix": "openai",
            "capabilities": ["chat", "streaming", "tool_calling", "structured_output", "vision", "audio_in", "reasoning"],
            "config": {"budget_enabled": True},
        },
        {
            "provider_id": "anthropic",
            "label": "Anthropic Claude",
            "transport": "litellm",
            "base_url": settings.litellm_proxy_url,
            "api_key_env": "ANTHROPIC_API_KEY",
            "default_model": os_env("ORQUESTRA_ANTHROPIC_MODEL", "claude-3-7-sonnet-latest"),
            "model_prefix": "anthropic",
            "capabilities": ["chat", "streaming", "tool_calling", "structured_output", "vision", "reasoning"],
            "config": {"prefer_native_tool_use": True},
        },
        {
            "provider_id": "deepseek",
            "label": "DeepSeek",
            "transport": "litellm",
            "base_url": settings.litellm_proxy_url,
            "api_key_env": "DEEPSEEK_API_KEY",
            "default_model": os_env("ORQUESTRA_DEEPSEEK_MODEL", settings.remote_chat_model),
            "model_prefix": "deepseek",
            "capabilities": ["chat", "streaming", "reasoning", "remote_only"],
            "config": {"low_cost": True},
        },
        {
            "provider_id": "ollama",
            "label": "Ollama",
            "transport": "litellm",
            "base_url": settings.litellm_proxy_url or os_env("ORQUESTRA_OLLAMA_BASE_URL", "http://localhost:11434"),
            "api_key_env": "OLLAMA_API_KEY",
            "default_model": os_env("ORQUESTRA_OLLAMA_MODEL", "qwen3:8b"),
            "model_prefix": "ollama",
            "capabilities": ["chat", "streaming", "local_only"],
            "config": {"optional": True},
        },
    ]

    for item in defaults:
        record = session.exec(select(ProviderProfile).where(ProviderProfile.provider_id == item["provider_id"])).first()
        if record:
            continue
        session.add(
            ProviderProfile(
                provider_id=item["provider_id"],
                label=item["label"],
                transport=item["transport"],
                base_url=item["base_url"],
                api_key_env=item["api_key_env"],
                default_model=item["default_model"],
                model_prefix=item["model_prefix"],
                capabilities_json=json.dumps(item["capabilities"], ensure_ascii=False),
                config_json=json.dumps(item["config"], ensure_ascii=False),
            )
        )
    session.commit()


def os_env(name: str, default: str) -> str:
    import os

    return os.getenv(name, default)


def list_gateway_providers(session: Session) -> list[GatewayProvider]:
    providers = session.exec(select(ProviderProfile).order_by(ProviderProfile.provider_id)).all()
    return [GatewayProvider.from_record(item) for item in providers]


@dataclass
class RagQueryOptions:
    question: str
    session_id: str | None = None
    collection_name: str | None = None
    provider_id: str | None = None
    model_name: str | None = None
    expected_output: str | None = None
    task_type: str = "generic"
    remember: bool = False
    mock_llm: bool = False
    memory_enabled: bool = True
    memory_scopes: list[str] | None = None
    include_workspace: bool = True
    include_sources: bool = True
    max_context_chars: int = 9000
    compaction_enabled: bool = True
    planner_enabled: bool = True
    task_context_enabled: bool = True
    memory_selector_mode: str = "hybrid"
    context_budget: int | None = None
    include_osint_evidence: bool = False
    investigation_id: str | None = None
    evidence_budget: int = 4
    fresh_web_enabled: bool = False
    source_registry_ids: list[str] | None = None
    enabled_connector_ids: list[str] | None = None
    via_tor: bool = False


class LocalRagEngine:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self.paths = RagPaths.load(settings.workspace_root)
        self.memory_graph = MemoryGraphService(settings)
        self.memory_recall = MemoryRecallService(settings)
        self.osint_service = OsintService(settings)
        self.planner = PlannerService()
        self.workspace_service = WorkspaceService(settings)

    def query(self, session: Session, options: RagQueryOptions, *, project_id: str | None = None) -> dict[str, Any]:
        rag_memory_payload: dict[str, Any] = {"items": [], "status": "disabled", "collection_name": "orquestra_memory_v1"}
        selector_mode = normalize_selector_mode(options.memory_selector_mode)
        context_sections: list[tuple[str, str]] = []
        workspace_context: dict[str, Any] = {"items": [], "context": "", "citations": []}
        legacy_sources: list[dict[str, Any]] = []
        osint_bundle: dict[str, Any] = {
            "investigation_id": options.investigation_id,
            "context": "",
            "citations": [],
            "evidence": [],
            "fresh_results": [],
            "status": "disabled",
            "selector_mode": "osint_hybrid",
        }
        session_snapshot: dict[str, Any] | None = None
        chat_session = None
        if options.session_id:
            from .models import ChatSession

            chat_session = session.get(ChatSession, options.session_id)
        if chat_session is not None:
            context_sections.append(("Perfil da sessão", profile_prompt_section(get_session_profile(chat_session))))
        if chat_session is not None and options.compaction_enabled:
            session_snapshot = self.memory_graph.build_context_snapshot(
                session,
                chat_session,
                context_budget=options.context_budget or options.max_context_chars,
            )
            snapshot_text = str(session_snapshot.get("context_text", "")).strip()
            if snapshot_text:
                context_sections.append(("Snapshot compacto", snapshot_text))
            if options.planner_enabled and options.task_context_enabled:
                planner_context = self.planner.task_prompt_context(session, chat_session.id)
                if planner_context:
                    context_sections.append(("Planner ativo", planner_context))
        if options.memory_enabled:
            rag_memory_payload = self.memory_recall.recall(
                session,
                query=options.question,
                project_id=project_id,
                session_id=options.session_id,
                scopes=options.memory_scopes or None,
                limit=6,
                selector_mode=selector_mode,
            )
            memory_context = self.memory_recall.format_context(
                rag_memory_payload.get("items", []),
                max_chars=min(max(options.max_context_chars // 3, 1000), 3500),
            )
            if memory_context:
                context_sections.append(("Memória relevante", memory_context))
        if options.include_osint_evidence:
            osint_bundle = self.osint_service.build_context_bundle(
                session,
                query=options.question,
                project_id=project_id,
                session_id=options.session_id,
                investigation_id=options.investigation_id,
                fresh_web_enabled=options.fresh_web_enabled,
                evidence_enabled=True,
                enabled_connector_ids=options.enabled_connector_ids,
                source_registry_ids=options.source_registry_ids,
                via_tor=options.via_tor,
                limit=max(1, options.evidence_budget),
            )
            if osint_bundle.get("context"):
                context_sections.append(("OSINT evidence", str(osint_bundle["context"])))
        if options.include_workspace:
            workspace_context = self.workspace_service.build_context_snippet(
                session,
                project_id=project_id,
                prompt=options.question,
                include_sources=options.include_sources,
                limit=4,
            )
            if workspace_context.get("context"):
                context_sections.append(("Workspace/fontes", str(workspace_context["context"])))
        if options.include_sources:
            legacy_sources = collect_legacy_rag_sources(
                self.settings,
                question=options.question,
                collection_names=[options.collection_name] if options.collection_name else list(DEFAULT_SOURCE_COLLECTIONS),
                limit=4,
            )
            legacy_context = format_retrieved_sources(legacy_sources, max_chars=min(max(options.max_context_chars // 3, 1000), 3500))
            if legacy_context:
                context_sections.append(("RAG legado", legacy_context))
        external_memory_context = build_context_block(context_sections, max_chars=options.max_context_chars)
        workflow = RagWorkflow(self.paths, mock_llm=options.mock_llm, provider_id=options.provider_id)
        result = workflow.invoke(
            question=options.question,
            session_id=options.session_id,
            collection_name=options.collection_name,
            model_name=options.model_name,
            provider_id=options.provider_id,
            expected_output=options.expected_output,
            task_type=options.task_type,
            remember=options.remember,
            external_memory_context=external_memory_context,
        )
        result["rag_memory"] = rag_memory_payload
        result["session_snapshot"] = session_snapshot
        result["osint"] = osint_bundle
        result["workspace_context"] = workspace_context
        result["legacy_sources"] = legacy_sources
        result["selector_mode"] = selector_mode
        result["context_sections"] = [{"title": title, "content": content} for title, content in context_sections if content]
        osint_citations = list(osint_bundle.get("citations", []))
        if osint_citations:
            result["citations"] = osint_citations + list(result.get("citations", []))
        if options.remember and options.session_id and result.get("answer"):
            self.memory_graph.create_training_candidate(
                session,
                project_id=project_id,
                session_id=options.session_id,
                source="rag_query",
                instruction=options.question,
                context="\n".join(item.get("source", "") or item.get("title", "") for item in result.get("citations", [])),
                response=result.get("answer", ""),
                labels={
                    "task_type": options.task_type,
                    "provider_id": result.get("provider_id"),
                    "model_name": result.get("model_name"),
                },
                approved=False,
                metadata={
                    "citations": result.get("citations", []),
                    "usage": result.get("usage", {}),
                },
            )
        return result


def ensure_runtime_dirs(settings: OrquestraSettings) -> None:
    settings.artifacts_root.mkdir(parents=True, exist_ok=True)
    rag_artifacts = settings.workspace_root / "experiments" / "orquestra" / "rag_exports"
    rag_artifacts.mkdir(parents=True, exist_ok=True)
    runtime_install_dir(settings).mkdir(parents=True, exist_ok=True)
    runtime_backup_dir(settings).mkdir(parents=True, exist_ok=True)
    settings.qdrant_path.mkdir(parents=True, exist_ok=True)
    memory_graph = MemoryGraphService(settings)
    memory_graph.paths.ensure()
    if settings.database_path is not None:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)


def collect_legacy_rag_sources(
    settings: OrquestraSettings,
    *,
    question: str,
    collection_names: list[str] | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    paths = RagPaths.load(settings.workspace_root)
    names = [name for name in (collection_names or list(DEFAULT_SOURCE_COLLECTIONS)) if isinstance(name, str) and name.strip()]
    if not question.strip() or not names:
        return []
    hits: list[dict[str, Any]] = []
    for collection_name in names[:2]:
        try:
            chunks = query_collection(paths, collection_name, question, top_k=max(limit, 2))
        except Exception:
            continue
        for chunk in chunks:
            hits.append(
                {
                    "channel": collection_name,
                    "source": chunk.metadata.get("source_path") or chunk.metadata.get("source_url") or chunk.metadata.get("source", ""),
                    "title": chunk.metadata.get("title") or chunk.metadata.get("rule_id") or chunk.metadata.get("document_id") or collection_name,
                    "excerpt": chunk.text,
                    "distance": float(chunk.distance) if chunk.distance is not None else None,
                }
            )
    return sorted(hits, key=lambda item: item["distance"] if item["distance"] is not None else 10_000.0)[:limit]


def format_retrieved_sources(
    items: list[dict[str, Any]],
    *,
    max_chars: int = 4000,
) -> str:
    rendered: list[str] = []
    total = 0
    for item in items:
        descriptor = item.get("source") or item.get("title") or item.get("channel") or "source"
        line = f"- [{item.get('channel', 'source')}] {descriptor}: {str(item.get('excerpt', '')).strip()}".strip()
        if total + len(line) > max_chars:
            break
        rendered.append(line)
        total += len(line)
    return "\n".join(rendered)


def build_context_block(sections: list[tuple[str, str]], *, max_chars: int = 9000) -> str:
    rendered = "\n\n".join(
        f"{title}:\n{content.strip()}"
        for title, content in sections
        if title and content and content.strip()
    ).strip()
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max_chars - 3].rstrip() + "..."


def model_artifact_to_dict(artifact: ModelArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "project_id": artifact.project_id,
        "name": artifact.name,
        "artifact_type": artifact.artifact_type,
        "source_pipeline": artifact.source_pipeline,
        "base_model": artifact.base_model,
        "storage_uri": artifact.storage_uri,
        "format": artifact.format,
        "benchmark": json.loads(artifact.benchmark_json or "{}"),
        "created_at": artifact.created_at.isoformat(),
    }


def memory_record_to_dict(record: MemoryRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "session_id": record.session_id,
        "topic_id": record.topic_id,
        "scope": record.scope,
        "memory_kind": record.memory_kind,
        "source": record.source,
        "content": record.content,
        "confidence": record.confidence,
        "ttl_seconds": record.ttl_seconds,
        "approved_for_training": record.approved_for_training,
        "metadata": json.loads(record.metadata_json or "{}"),
        "created_at": record.created_at.isoformat(),
    }


def memory_review_candidate_to_dict(candidate: MemoryReviewCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "project_id": candidate.project_id,
        "session_id": candidate.session_id,
        "scope": candidate.scope,
        "memory_kind": candidate.memory_kind,
        "title": candidate.title,
        "content": candidate.content,
        "rationale": candidate.rationale,
        "source_message_ids": json.loads(candidate.source_message_ids_json or "[]"),
        "citations": json.loads(candidate.citations_json or "[]"),
        "confidence": candidate.confidence,
        "status": candidate.status,
        "metadata": json.loads(candidate.metadata_json or "{}"),
        "created_at": candidate.created_at.isoformat(),
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
    }


def memory_topic_to_dict(topic: MemoryTopic) -> dict[str, Any]:
    return {
        "id": topic.id,
        "project_id": topic.project_id,
        "scope": topic.scope,
        "slug": topic.slug,
        "title": topic.title,
        "description": topic.description,
        "topic_path": topic.topic_path,
        "manifest_path": topic.manifest_path,
        "metadata": json.loads(topic.metadata_json or "{}"),
        "last_used_at": topic.last_used_at.isoformat(),
        "updated_at": topic.updated_at.isoformat(),
    }


def memory_manifest_entry_to_dict(entry: MemoryManifestEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "topic_id": entry.topic_id,
        "entry_kind": entry.entry_kind,
        "label": entry.label,
        "summary": entry.summary,
        "source_ref": entry.source_ref,
        "relevance": entry.relevance,
        "metadata": json.loads(entry.metadata_json or "{}"),
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def session_transcript_to_dict(item: SessionTranscript) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "storage_path": item.storage_path,
        "message_count": item.message_count,
        "transcript_bytes": item.transcript_bytes,
        "last_message_id": item.last_message_id,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def session_summary_to_dict(item: SessionSummary) -> dict[str, Any]:
    sections = json.loads(item.sections_json or "{}")
    metadata = json.loads(item.metadata_json or "{}")
    return {
        "id": item.id,
        "session_id": item.session_id,
        "summary_path": item.summary_path,
        "current_state": item.current_state,
        "sections": sections,
        "objective": sections.get("objective", ""),
        "decisions": sections.get("decisions", ""),
        "open_questions": sections.get("open_questions", ""),
        "next_steps": sections.get("next_steps", ""),
        "relevant_files": [
            line.lstrip("- ").strip()
            for line in str(sections.get("files_and_functions", "")).splitlines()
            if line.strip() and "Nenhum" not in line
        ],
        "commands_run": [
            line.lstrip("- ").strip()
            for line in str(sections.get("workflow", "")).splitlines()
            if line.strip() and "Fluxo ainda" not in line
        ],
        "errors_and_fixes": [
            line.lstrip("- ").strip()
            for line in str(sections.get("recent_failures", sections.get("errors_and_corrections", ""))).splitlines()
            if line.strip() and "Sem falhas" not in line and "Sem erros" not in line
        ],
        "worklog": [
            line.lstrip("- ").strip()
            for line in str(sections.get("worklog", "")).splitlines()
            if line.strip()
        ],
        "compacted_from_message_count": int(metadata.get("compacted_message_count", 0) or 0),
        "last_message_id": item.last_message_id,
        "metadata": metadata,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def compaction_state_to_dict(item: SessionCompactionState) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "last_compacted_message_id": item.last_compacted_message_id,
        "summary_version": item.summary_version,
        "next_steps": json.loads(item.next_steps_json or "[]"),
        "preserved_recent_turns": item.preserved_recent_turns,
        "compacted_message_count": item.compacted_message_count,
        "compacted_at": item.compacted_at.isoformat(),
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def planner_snapshot_to_dict(item: PlannerSnapshot) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "objective": item.objective,
        "strategy": item.strategy,
        "next_steps": json.loads(item.next_steps_json or "[]"),
        "risks": json.loads(item.risks_json or "[]"),
        "metadata": json.loads(item.metadata_json or "{}"),
        "last_planned_at": item.last_planned_at.isoformat(),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def session_task_to_dict(item: SessionTask) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "subject": item.subject,
        "description": item.description,
        "active_form": item.active_form,
        "status": item.status,
        "owner": item.owner,
        "blocked_by": json.loads(item.blocked_by_json or "[]"),
        "blocks": json.loads(item.blocks_json or "[]"),
        "position": item.position,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def workflow_step_run_to_dict(item: WorkflowStepRun) -> dict[str, Any]:
    return {
        "id": item.id,
        "run_id": item.run_id,
        "step_index": item.step_index,
        "step_type": item.step_type,
        "label": item.label,
        "status": item.status,
        "input": json.loads(item.input_json or "{}"),
        "output": json.loads(item.output_json or "{}"),
        "metadata": json.loads(item.metadata_json or "{}"),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
    }


def workflow_run_to_dict(item: WorkflowRun, *, steps: list[WorkflowStepRun] | None = None) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "task_id": item.task_id,
        "workflow_name": item.workflow_name,
        "status": item.status,
        "summary": item.summary,
        "log_path": item.log_path,
        "output_path": item.output_path,
        "progress": item.progress,
        "cancel_requested": item.cancel_requested,
        "metadata": json.loads(item.metadata_json or "{}"),
        "started_at": item.started_at.isoformat(),
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "steps": [workflow_step_run_to_dict(step) for step in (steps or [])],
    }


def training_candidate_to_dict(item: TrainingCandidate) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "session_id": item.session_id,
        "source": item.source,
        "instruction": item.instruction,
        "context": item.context,
        "response": item.response,
        "labels": json.loads(item.labels_json or "{}"),
        "approved": item.approved,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def job_record_to_dict(record: JobRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "job_family": record.job_family,
        "connector": record.connector,
        "status": record.status,
        "spec": json.loads(record.spec_json or "{}"),
        "logs_path": record.logs_path,
        "outputs": json.loads(record.outputs_json or "{}"),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def provider_profile_to_dict(record: ProviderProfile) -> dict[str, Any]:
    return {
        "id": record.id,
        "provider_id": record.provider_id,
        "label": record.label,
        "transport": record.transport,
        "base_url": record.base_url,
        "api_key_env": record.api_key_env,
        "default_model": record.default_model,
        "model_prefix": record.model_prefix,
        "enabled": record.enabled,
        "capabilities": json.loads(record.capabilities_json or "[]"),
        "config": json.loads(record.config_json or "{}"),
        "updated_at": record.updated_at.isoformat(),
    }


def project_to_dict(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "description": project.description,
        "default_provider_id": project.default_provider_id,
        "default_model": project.default_model,
        "created_at": project.created_at.isoformat(),
    }


def workspace_scan_to_dict(item: WorkspaceScan) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "root_path": item.root_path,
        "prompt_hint": item.prompt_hint,
        "status": item.status,
        "total_assets": item.total_assets,
        "total_bytes": item.total_bytes,
        "inventory_path": item.inventory_path,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def workspace_asset_to_dict(item: WorkspaceAsset) -> dict[str, Any]:
    return {
        "id": item.id,
        "scan_id": item.scan_id,
        "absolute_path": item.absolute_path,
        "relative_path": item.relative_path,
        "parent_relative_path": item.parent_relative_path,
        "asset_kind": item.asset_kind,
        "mime_type": item.mime_type,
        "extension": item.extension,
        "size_bytes": item.size_bytes,
        "sha256": item.sha256,
        "depth": item.depth,
        "modified_at": item.modified_at.isoformat(),
        "title": item.title,
        "summary_excerpt": item.summary_excerpt,
        "extraction_state": item.extraction_state,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def workspace_derivative_to_dict(item: WorkspaceDerivative) -> dict[str, Any]:
    return {
        "id": item.id,
        "asset_id": item.asset_id,
        "derivative_kind": item.derivative_kind,
        "storage_path": item.storage_path,
        "media_type": item.media_type,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
    }


def workspace_insight_to_dict(item: WorkspaceInsight) -> dict[str, Any]:
    return {
        "id": item.id,
        "scan_id": item.scan_id,
        "asset_id": item.asset_id,
        "kind": item.kind,
        "title": item.title,
        "content": item.content,
        "relevance": item.relevance,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
    }
