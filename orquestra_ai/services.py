from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from rag.common import RagPaths
from rag.graph import RagWorkflow

from .config import OrquestraSettings
from .gateway import GatewayProvider
from .memory_graph import MemoryGraphService
from .models import (
    JobRecord,
    MemoryManifestEntry,
    MemoryRecord,
    MemoryTopic,
    ModelArtifact,
    Project,
    ProjectDeployment,
    ProviderProfile,
    SessionSummary,
    SessionTranscript,
    TrainingCandidate,
    WorkspaceAsset,
    WorkspaceDerivative,
    WorkspaceInsight,
    WorkspaceScan,
)


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


class LocalRagEngine:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self.paths = RagPaths.load(settings.workspace_root)
        self.memory_graph = MemoryGraphService(settings)

    def query(self, session: Session, options: RagQueryOptions, *, project_id: str | None = None) -> dict[str, Any]:
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
        )
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
    settings.qdrant_path.mkdir(parents=True, exist_ok=True)
    memory_graph = MemoryGraphService(settings)
    memory_graph.paths.ensure()
    if settings.database_path is not None:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)


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
        "source": record.source,
        "content": record.content,
        "confidence": record.confidence,
        "ttl_seconds": record.ttl_seconds,
        "approved_for_training": record.approved_for_training,
        "metadata": json.loads(record.metadata_json or "{}"),
        "created_at": record.created_at.isoformat(),
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
    return {
        "id": item.id,
        "session_id": item.session_id,
        "summary_path": item.summary_path,
        "current_state": item.current_state,
        "sections": json.loads(item.sections_json or "{}"),
        "last_message_id": item.last_message_id,
        "metadata": json.loads(item.metadata_json or "{}"),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
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
