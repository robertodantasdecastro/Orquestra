from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .config import OrquestraSettings, load_settings
from .connectors import list_connector_descriptors
from .db import build_engine, init_database
from .gateway import GatewayLlmError, OrquestraGateway
from .memory_graph import MemoryGraphService
from .models import (
    ChatMessage,
    ChatSession,
    JobRecord,
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
    WorkspaceInsight,
    WorkspaceScan,
    utc_now,
)
from .operations import OrquestraOperations
from .services import (
    LocalRagEngine,
    RagQueryOptions,
    ensure_runtime_dirs,
    job_record_to_dict,
    list_gateway_providers,
    memory_record_to_dict,
    memory_topic_to_dict,
    model_artifact_to_dict,
    project_to_dict,
    provider_profile_to_dict,
    seed_default_state,
    session_summary_to_dict,
    session_transcript_to_dict,
    training_candidate_to_dict,
    workspace_asset_to_dict,
    workspace_insight_to_dict,
    workspace_scan_to_dict,
)
from .workspace import WorkspaceService


class ProviderUpsertRequest(BaseModel):
    provider_id: str
    label: str
    transport: str = "litellm"
    base_url: str | None = None
    api_key_env: str | None = None
    default_model: str | None = None
    model_prefix: str | None = None
    enabled: bool = True
    capabilities: list[str] = Field(default_factory=list)
    config: dict[str, object] = Field(default_factory=dict)


class ProjectCreateRequest(BaseModel):
    slug: str
    name: str
    description: str = ""
    default_provider_id: str = "lmstudio"
    default_model: str = "ministral"


class ChatSessionCreateRequest(BaseModel):
    project_id: str | None = None
    title: str = "Nova sessão"
    provider_id: str | None = None
    model_name: str | None = None


class ChatMessagePayload(BaseModel):
    id: str
    role: str
    content: str
    provider_id: str | None = None
    model_name: str | None = None
    usage: dict[str, object] = Field(default_factory=dict)
    latency_seconds: float | None = None
    created_at: str


class ChatStreamRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    provider_id: str | None = None
    model_name: str | None = None
    message: str
    temperature: float = 0.1
    max_tokens: int = 700
    remember: bool = False
    mock_response: bool = False


class MemoryUpsertRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    topic_id: str | None = None
    scope: str
    source: str = "manual"
    content: str
    confidence: float = 0.5
    ttl_seconds: int | None = None
    approved_for_training: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class MemoryRecallRequest(BaseModel):
    query: str
    project_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    limit: int = 6


class MemoryPromoteRequest(BaseModel):
    project_id: str | None = None
    scope: str = "project_memory"
    title: str
    content: str
    source: str = "manual"
    metadata: dict[str, object] = Field(default_factory=dict)


class TrainingCandidateCreateRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    source: str = "manual"
    instruction: str
    context: str = ""
    response: str
    labels: dict[str, object] = Field(default_factory=dict)
    approved: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class RagQueryRequest(BaseModel):
    question: str
    project_id: str | None = None
    session_id: str | None = None
    collection_name: str | None = None
    provider_id: str | None = None
    model_name: str | None = None
    expected_output: str | None = None
    task_type: str = "generic"
    remember: bool = False
    mock_llm: bool = False


class JobCreateRequest(BaseModel):
    project_id: str | None = None
    connector: str
    spec: dict[str, object] = Field(default_factory=dict)


class ModelArtifactCreateRequest(BaseModel):
    project_id: str | None = None
    name: str
    artifact_type: str
    source_pipeline: str = "manual"
    base_model: str = ""
    storage_uri: str = ""
    format: str = "adapter-only"
    benchmark: dict[str, object] = Field(default_factory=dict)


class DeploymentCreateRequest(BaseModel):
    artifact_id: str
    environment: str = "local"
    notes: str = ""


class RegistryCompareRequest(BaseModel):
    baseline_artifact_id: str
    candidate_artifact_id: str


class WorkspaceAttachRequest(BaseModel):
    project_id: str | None = None
    root_path: str
    prompt_hint: str = ""


class WorkspaceQueryRequest(BaseModel):
    scan_id: str
    prompt: str
    provider_id: str | None = None
    model_name: str | None = None
    force_extract: bool = False
    mock_response: bool = False


class WorkspaceExtractRequest(BaseModel):
    prompt_hint: str = ""
    force: bool = False


class WorkspaceMemorizeRequest(BaseModel):
    project_id: str | None = None
    scope: str = "workspace_memory"
    source: str = "workspace"


class OperationRunRequest(BaseModel):
    action_id: str


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _compact_usage(usage: dict[str, object]) -> dict[str, object]:
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def _best_preview_path(asset: WorkspaceAsset, derivatives: list[dict[str, object]]) -> Path | None:
    preferred_kinds = {
        "image": ["thumbnail"],
        "pdf": ["text_extract"],
        "office": ["text_extract"],
        "audio": ["transcript"],
        "video": ["poster_frame", "transcript"],
        "code_text": [],
        "binary": [],
    }
    for kind in preferred_kinds.get(asset.asset_kind, []):
        match = next((item for item in derivatives if item["kind"] == kind), None)
        if match:
            path = Path(str(match["storage_path"]))
            if path.exists():
                return path
    path = Path(asset.absolute_path)
    return path if path.exists() else None


def create_app(settings: OrquestraSettings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    ensure_runtime_dirs(app_settings)
    engine = build_engine(app_settings.database_url)
    memory_graph = MemoryGraphService(app_settings)
    workspace_service = WorkspaceService(app_settings)
    operations = OrquestraOperations(app_settings)

    def bootstrap_runtime() -> None:
        init_database(engine)
        with Session(engine) as session:
            seed_default_state(session, app_settings)
            workspace_service.gc_derivatives(session)
            session.commit()

    app = FastAPI(
        title="Orquestra AI",
        version="0.2.0",
        description="Control plane unificado do Orquestra.",
    )
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.memory_graph = memory_graph
    app.state.workspace_service = workspace_service
    app.state.operations = operations
    bootstrap_runtime()

    frontend_dist = app_settings.workspace_root / "orquestra_web" / "dist"
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="orquestra-assets")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        bootstrap_runtime()

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        try:
            memory_graph.index.close()
        except Exception:
            pass
        try:
            workspace_service.index.close()
        except Exception:
            pass

    def get_session(request: Request) -> Iterator[Session]:
        with Session(request.app.state.engine) as session:
            yield session

    def get_gateway(session: Session = Depends(get_session)) -> OrquestraGateway:
        providers = list_gateway_providers(session)
        return OrquestraGateway(providers)

    @app.get("/api/health")
    def api_health(session: Session = Depends(get_session)) -> dict[str, object]:
        provider_count = len(session.exec(select(ProviderProfile)).all())
        project_count = len(session.exec(select(Project)).all())
        topic_count = len(session.exec(select(MemoryTopic)).all())
        scan_count = len(session.exec(select(WorkspaceScan)).all())
        return {
            "ok": True,
            "app": "Orquestra AI",
            "workspace_root": str(app_settings.workspace_root),
            "database_url": app_settings.database_url,
            "redis_url": app_settings.redis_url,
            "qdrant_url": app_settings.qdrant_url,
            "qdrant_path": str(app_settings.qdrant_path),
            "web_enabled": app_settings.web_enabled,
            "providers": provider_count,
            "projects": project_count,
            "memory_topics": topic_count,
            "workspace_scans": scan_count,
        }

    @app.get("/api/ops/dashboard")
    def ops_dashboard(session: Session = Depends(get_session)) -> dict[str, object]:
        return operations.dashboard(session)

    @app.get("/api/ops/actions")
    def ops_actions() -> list[dict[str, object]]:
        return operations.list_actions()

    @app.get("/api/ops/runs")
    def ops_runs() -> list[dict[str, object]]:
        return operations.list_runs()

    @app.get("/api/ops/runs/{run_id}")
    def ops_run(run_id: str) -> dict[str, object]:
        try:
            return operations.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Execução operacional não encontrada.") from exc

    @app.post("/api/ops/runs")
    def create_ops_run(payload: OperationRunRequest) -> dict[str, object]:
        try:
            return operations.start_action(payload.action_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Ação operacional não encontrada.") from exc

    @app.get("/", response_model=None)
    def serve_frontend():
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return JSONResponse(
            {
                "ok": True,
                "app": "Orquestra AI",
                "message": "Frontend ainda nao foi buildado. Use scripts/start_orquestra_web.sh para o modo web.",
            }
        )

    @app.get("/api/providers")
    def list_providers(session: Session = Depends(get_session)) -> list[dict[str, object]]:
        rows = session.exec(select(ProviderProfile).order_by(ProviderProfile.provider_id)).all()
        return [provider_profile_to_dict(row) for row in rows]

    @app.put("/api/providers")
    def upsert_provider(payload: ProviderUpsertRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        record = session.exec(select(ProviderProfile).where(ProviderProfile.provider_id == payload.provider_id)).first()
        if record is None:
            record = ProviderProfile(provider_id=payload.provider_id, label=payload.label)
            session.add(record)
        record.label = payload.label
        record.transport = payload.transport
        record.base_url = payload.base_url
        record.api_key_env = payload.api_key_env
        record.default_model = payload.default_model
        record.model_prefix = payload.model_prefix
        record.enabled = payload.enabled
        record.capabilities_json = json.dumps(payload.capabilities, ensure_ascii=False)
        record.config_json = json.dumps(payload.config, ensure_ascii=False)
        record.updated_at = utc_now()
        session.commit()
        session.refresh(record)
        return provider_profile_to_dict(record)

    @app.get("/api/models")
    def list_models(provider_id: str | None = None, gateway: OrquestraGateway = Depends(get_gateway)) -> dict[str, object]:
        return {"provider_id": provider_id or gateway.default_provider_id, "models": gateway.list_models(provider_id)}

    @app.get("/api/connectors")
    def list_connectors() -> list[dict[str, object]]:
        return [item.to_dict() for item in list_connector_descriptors()]

    @app.get("/api/projects")
    def list_projects(session: Session = Depends(get_session)) -> list[dict[str, object]]:
        projects = session.exec(select(Project).order_by(Project.created_at)).all()
        return [project_to_dict(project) for project in projects]

    @app.post("/api/projects")
    def create_project(payload: ProjectCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        existing = session.exec(select(Project).where(Project.slug == payload.slug)).first()
        if existing:
            raise HTTPException(status_code=409, detail="Projeto com esse slug ja existe.")
        project = Project(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            default_provider_id=payload.default_provider_id,
            default_model=payload.default_model,
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        return project_to_dict(project)

    @app.post("/api/chat/sessions")
    def create_chat_session(payload: ChatSessionCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        provider_id = payload.provider_id or app_settings.default_provider_id
        model_name = payload.model_name or app_settings.local_chat_model
        record = ChatSession(
            project_id=payload.project_id,
            title=payload.title,
            provider_id=provider_id,
            model_name=model_name,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return {
            "id": record.id,
            "project_id": record.project_id,
            "title": record.title,
            "provider_id": record.provider_id,
            "model_name": record.model_name,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "status": record.status,
        }

    @app.get("/api/chat/sessions")
    def list_chat_sessions(project_id: str | None = None, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        statement = select(ChatSession).order_by(ChatSession.updated_at.desc())
        if project_id:
            statement = statement.where(ChatSession.project_id == project_id)
        rows = session.exec(statement.limit(100)).all()
        return [
            {
                "id": row.id,
                "project_id": row.project_id,
                "title": row.title,
                "provider_id": row.provider_id,
                "model_name": row.model_name,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "status": row.status,
            }
            for row in rows
        ]

    @app.get("/api/chat/sessions/{session_id}/messages")
    def list_chat_messages(session_id: str, session: Session = Depends(get_session)) -> list[ChatMessagePayload]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        rows = session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)).all()
        return [
            ChatMessagePayload(
                id=row.id,
                role=row.role,
                content=row.content,
                provider_id=row.provider_id,
                model_name=row.model_name,
                usage=json.loads(row.usage_json or "{}"),
                latency_seconds=row.latency_seconds,
                created_at=row.created_at.isoformat(),
            )
            for row in rows
        ]

    @app.post("/api/chat/sessions/{session_id}/resume")
    def resume_chat_session(session_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        payload = memory_graph.build_resume_payload(session, chat_session)
        session.commit()
        return payload

    @app.get("/api/chat/sessions/{session_id}/transcript")
    def get_chat_transcript(session_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        transcript = session.exec(select(SessionTranscript).where(SessionTranscript.session_id == session_id)).first()
        payload = session_transcript_to_dict(transcript) if transcript else {
            "session_id": session_id,
            "storage_path": str(memory_graph.transcript_path(session_id)),
            "message_count": 0,
            "transcript_bytes": 0,
            "metadata": {},
        }
        payload["entries"] = memory_graph.list_transcript_messages(session_id)
        return payload

    @app.get("/api/chat/sessions/{session_id}/summary")
    def get_chat_summary(session_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        summary = session.exec(select(SessionSummary).where(SessionSummary.session_id == session_id)).first()
        if summary is None:
            summary = memory_graph.get_or_build_summary(session, chat_session)
            session.commit()
            session.refresh(summary)
        return session_summary_to_dict(summary)

    @app.post("/api/chat/stream")
    def chat_stream(
        payload: ChatStreamRequest,
        session: Session = Depends(get_session),
    ) -> StreamingResponse:
        project = None
        if payload.project_id:
            project = session.get(Project, payload.project_id)
            if project is None:
                raise HTTPException(status_code=404, detail="Projeto nao encontrado.")
        provider_id = payload.provider_id or (project.default_provider_id if project else app_settings.default_provider_id)
        model_name = payload.model_name or (project.default_model if project else app_settings.local_chat_model)

        chat_session = session.get(ChatSession, payload.session_id) if payload.session_id else None
        if chat_session is None:
            chat_session = ChatSession(
                project_id=payload.project_id,
                title=payload.message[:60] or "Nova sessão",
                provider_id=provider_id,
                model_name=model_name,
            )
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)

        summary = memory_graph.get_or_build_summary(session, chat_session)
        recalled = memory_graph.recall_memories(
            session,
            query=payload.message,
            project_id=payload.project_id,
            scopes=[],
            limit=4,
        )
        memory_context = "\n".join(
            f"- {item['title']}: {item['content']}" for item in recalled
        ).strip()

        gateway = OrquestraGateway(list_gateway_providers(session), mock=payload.mock_response)
        user_message = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content=payload.message,
            metadata_json=json.dumps({"recalled_memories": recalled}, ensure_ascii=False),
        )
        session.add(user_message)
        session.flush()
        memory_graph.append_transcript_message(session, chat_session, user_message, metadata={"kind": "user_turn"})

        try:
            response = gateway.generate(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Voce e o assistente multitarefa do Orquestra AI. "
                            "Use o resumo de sessao e a memoria duravel apenas quando realmente ajudarem. "
                            "Se citar arquivos, seja especifico e operacional."
                        ),
                    },
                    {
                        "role": "user",
                        "content": "\n\n".join(
                            part
                            for part in (
                                f"Resumo da sessao:\n{summary.current_state}" if summary.current_state else "",
                                f"Memorias relevantes:\n{memory_context}" if memory_context else "",
                                f"Mensagem atual:\n{payload.message}",
                            )
                            if part
                        ),
                    },
                ],
                provider_id=provider_id,
                model_name=model_name,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                fallback_text="Resposta simulada do control plane.",
            )
        except GatewayLlmError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        assistant_message = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content=response.content,
            provider_id=response.provider_id,
            model_name=response.model_name,
            usage_json=json.dumps(response.usage, ensure_ascii=False),
            latency_seconds=response.latency_seconds,
            metadata_json=json.dumps({"memory_recall": recalled}, ensure_ascii=False),
        )
        chat_session.updated_at = utc_now()
        chat_session.last_message_at = utc_now()
        session.add(assistant_message)
        session.flush()
        memory_graph.append_transcript_message(
            session,
            chat_session,
            assistant_message,
            metadata={"kind": "assistant_turn", "usage": _compact_usage(response.usage)},
        )
        updated_summary = memory_graph.build_session_summary(session, chat_session)

        if payload.remember:
            record = MemoryRecord(
                project_id=payload.project_id,
                session_id=chat_session.id,
                scope="episodic_memory",
                source=f"chat:{chat_session.id}",
                content=f"Pergunta: {payload.message}\n\nResposta: {response.content}",
                confidence=0.72,
                approved_for_training=False,
                metadata_json=json.dumps(
                    {
                        "provider_id": provider_id,
                        "model_name": model_name,
                        "latency_seconds": response.latency_seconds,
                        "usage": response.usage,
                    },
                    ensure_ascii=False,
                ),
            )
            session.add(record)
            memory_graph.create_training_candidate(
                session,
                project_id=payload.project_id,
                session_id=chat_session.id,
                source="chat_stream",
                instruction=payload.message,
                context=summary.current_state,
                response=response.content,
                labels={
                    "provider_id": response.provider_id,
                    "model_name": response.model_name,
                    "memory_used": bool(recalled),
                },
                metadata={
                    "usage": response.usage,
                    "recalled_memories": recalled,
                },
            )
        session.commit()

        def event_stream() -> Iterator[str]:
            yield _sse(
                "session",
                {
                    "session_id": chat_session.id,
                    "provider_id": provider_id,
                    "model_name": model_name,
                },
            )
            words = response.content.split()
            for index in range(0, len(words), 12):
                chunk = " ".join(words[index : index + 12])
                yield _sse("delta", {"content": chunk})
            yield _sse(
                "summary",
                {
                    "current_state": updated_summary.current_state,
                    "updated_at": updated_summary.updated_at.isoformat(),
                },
            )
            yield _sse(
                "done",
                {
                    "provider_id": response.provider_id,
                    "model_name": response.model_name,
                    "usage": response.usage,
                    "latency_seconds": response.latency_seconds,
                },
            )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/api/memory")
    def list_memory(
        project_id: str | None = None,
        scope: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        statement = select(MemoryRecord).order_by(MemoryRecord.created_at.desc())
        if project_id:
            statement = statement.where(MemoryRecord.project_id == project_id)
        if scope:
            statement = statement.where(MemoryRecord.scope == scope)
        rows = session.exec(statement.limit(120)).all()
        return [memory_record_to_dict(row) for row in rows]

    @app.post("/api/memory/upsert")
    def upsert_memory(payload: MemoryUpsertRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        record = MemoryRecord(
            project_id=payload.project_id,
            session_id=payload.session_id,
            topic_id=payload.topic_id,
            scope=payload.scope,
            source=payload.source,
            content=payload.content,
            confidence=payload.confidence,
            ttl_seconds=payload.ttl_seconds,
            approved_for_training=payload.approved_for_training,
            metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return memory_record_to_dict(record)

    @app.get("/api/memory/topics")
    def list_memory_topics(
        project_id: str | None = None,
        scope: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        statement = select(MemoryTopic).order_by(MemoryTopic.updated_at.desc())
        if project_id:
            statement = statement.where(MemoryTopic.project_id == project_id)
        if scope:
            statement = statement.where(MemoryTopic.scope == scope)
        rows = session.exec(statement.limit(100)).all()
        return [memory_topic_to_dict(row) for row in rows]

    @app.post("/api/memory/recall")
    def recall_memory(payload: MemoryRecallRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        rows = memory_graph.recall_memories(
            session,
            query=payload.query,
            project_id=payload.project_id,
            scopes=payload.scopes,
            limit=payload.limit,
        )
        return {"query": payload.query, "items": rows}

    @app.post("/api/memory/promote")
    def promote_memory(payload: MemoryPromoteRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        topic, _, record = memory_graph.promote_to_topic(
            session,
            project_id=payload.project_id,
            scope=payload.scope,
            title=payload.title,
            content=payload.content,
            source=payload.source,
            metadata=payload.metadata,
        )
        session.commit()
        session.refresh(topic)
        session.refresh(record)
        return {
            "topic": memory_topic_to_dict(topic),
            "record": memory_record_to_dict(record),
        }

    @app.get("/api/memory/training-candidates")
    def list_training_candidates(project_id: str | None = None, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        statement = select(TrainingCandidate).order_by(TrainingCandidate.created_at.desc())
        if project_id:
            statement = statement.where(TrainingCandidate.project_id == project_id)
        rows = session.exec(statement.limit(120)).all()
        return [training_candidate_to_dict(row) for row in rows]

    @app.post("/api/memory/training-candidates")
    def create_training_candidate(payload: TrainingCandidateCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        record = memory_graph.create_training_candidate(
            session,
            project_id=payload.project_id,
            session_id=payload.session_id,
            source=payload.source,
            instruction=payload.instruction,
            context=payload.context,
            response=payload.response,
            labels=payload.labels,
            approved=payload.approved,
            metadata=payload.metadata,
        )
        session.commit()
        session.refresh(record)
        return training_candidate_to_dict(record)

    @app.post("/api/rag/query")
    def rag_query(payload: RagQueryRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        engine_service = LocalRagEngine(app_settings)
        result = engine_service.query(
            session,
            RagQueryOptions(
                question=payload.question,
                session_id=payload.session_id,
                collection_name=payload.collection_name,
                provider_id=payload.provider_id,
                model_name=payload.model_name,
                expected_output=payload.expected_output,
                task_type=payload.task_type,
                remember=payload.remember,
                mock_llm=payload.mock_llm,
            ),
            project_id=payload.project_id,
        )
        session.commit()
        return JSONResponse(result)

    @app.get("/api/workspace/scans")
    def list_workspace_scans(project_id: str | None = None, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        statement = select(WorkspaceScan).order_by(WorkspaceScan.created_at.desc())
        if project_id:
            statement = statement.where(WorkspaceScan.project_id == project_id)
        rows = session.exec(statement.limit(50)).all()
        return [workspace_scan_to_dict(row) for row in rows]

    @app.post("/api/workspace/attach-directory")
    def attach_workspace_directory(payload: WorkspaceAttachRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            scan = workspace_service.attach_directory(
                session,
                root_path=payload.root_path,
                project_id=payload.project_id,
                prompt_hint=payload.prompt_hint,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session.commit()
        session.refresh(scan)
        return workspace_scan_to_dict(scan)

    @app.get("/api/workspace/scans/{scan_id}")
    def get_workspace_scan(scan_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        scan = session.get(WorkspaceScan, scan_id)
        if scan is None:
            raise HTTPException(status_code=404, detail="Workspace scan nao encontrado.")
        insights = session.exec(select(WorkspaceInsight).where(WorkspaceInsight.scan_id == scan_id).order_by(WorkspaceInsight.created_at.desc())).all()
        payload = workspace_scan_to_dict(scan)
        payload["insights"] = [workspace_insight_to_dict(item) for item in insights[:20]]
        return payload

    @app.get("/api/workspace/assets")
    def list_workspace_assets(
        scan_id: str,
        asset_kind: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        statement = select(WorkspaceAsset).where(WorkspaceAsset.scan_id == scan_id).order_by(WorkspaceAsset.relative_path)
        if asset_kind:
            statement = statement.where(WorkspaceAsset.asset_kind == asset_kind)
        rows = session.exec(statement.limit(2000)).all()
        return [workspace_asset_to_dict(row) for row in rows]

    @app.post("/api/workspace/query")
    def query_workspace(
        payload: WorkspaceQueryRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        gateway = OrquestraGateway(list_gateway_providers(session), mock=payload.mock_response)
        try:
            response = workspace_service.query_workspace(
                session,
                gateway,
                scan_id=payload.scan_id,
                prompt=payload.prompt,
                provider_id=payload.provider_id or app_settings.default_provider_id,
                model_name=payload.model_name or app_settings.local_chat_model,
                force_extract=payload.force_extract,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.commit()
        return response

    @app.post("/api/workspace/assets/{asset_id}/extract")
    def extract_workspace_asset(asset_id: str, payload: WorkspaceExtractRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        asset = session.get(WorkspaceAsset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset nao encontrado.")
        result = workspace_service.extract_asset(session, asset, force=payload.force, prompt_hint=payload.prompt_hint)
        session.commit()
        session.refresh(asset)
        return result

    @app.get("/api/workspace/assets/{asset_id}/preview")
    def preview_workspace_asset(
        asset_id: str,
        raw: bool = Query(default=False),
        session: Session = Depends(get_session),
    ):
        asset = session.get(WorkspaceAsset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset nao encontrado.")
        preview = workspace_service.preview_asset(session, asset)
        if raw:
            preview_path = _best_preview_path(asset, preview.get("derivatives", []))
            if preview_path is None:
                raise HTTPException(status_code=404, detail="Preview indisponivel para este asset.")
            return FileResponse(preview_path, media_type=asset.mime_type or None, filename=Path(asset.absolute_path).name)
        return preview

    @app.post("/api/workspace/assets/{asset_id}/open")
    def open_workspace_asset(asset_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        asset = session.get(WorkspaceAsset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset nao encontrado.")
        try:
            return workspace_service.open_asset(asset)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/workspace/assets/{asset_id}/memorize")
    def memorize_workspace_asset(asset_id: str, payload: WorkspaceMemorizeRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        asset = session.get(WorkspaceAsset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset nao encontrado.")
        record = workspace_service.memorize_asset(
            session,
            asset,
            project_id=payload.project_id,
            scope=payload.scope,
            source=payload.source,
        )
        session.commit()
        session.refresh(record)
        return memory_record_to_dict(record)

    @app.get("/api/training/jobs")
    def list_training_jobs(session: Session = Depends(get_session)) -> list[dict[str, object]]:
        jobs = session.exec(
            select(JobRecord).where(JobRecord.job_family == "training").order_by(JobRecord.created_at.desc())
        ).all()
        return [job_record_to_dict(job) for job in jobs]

    @app.post("/api/training/jobs")
    def create_training_job(payload: JobCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        job = JobRecord(
            project_id=payload.project_id,
            job_family="training",
            connector=payload.connector,
            status="queued",
            spec_json=json.dumps(payload.spec, ensure_ascii=False),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job_record_to_dict(job)

    @app.get("/api/remote/jobs")
    def list_remote_jobs(session: Session = Depends(get_session)) -> list[dict[str, object]]:
        jobs = session.exec(select(JobRecord).where(JobRecord.job_family == "remote").order_by(JobRecord.created_at.desc())).all()
        return [job_record_to_dict(job) for job in jobs]

    @app.post("/api/remote/jobs")
    def create_remote_job(payload: JobCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        job = JobRecord(
            project_id=payload.project_id,
            job_family="remote",
            connector=payload.connector,
            status="queued_waiting_compute",
            spec_json=json.dumps(payload.spec, ensure_ascii=False),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job_record_to_dict(job)

    @app.get("/api/remote/jobs/{job_id}/logs")
    def get_remote_job_logs(job_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        job = session.get(JobRecord, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job nao encontrado.")
        if not job.logs_path:
            return {"job_id": job_id, "logs_path": None, "content": ""}
        path = Path(job.logs_path)
        if not path.exists():
            return {"job_id": job_id, "logs_path": job.logs_path, "content": ""}
        return {"job_id": job_id, "logs_path": job.logs_path, "content": path.read_text(encoding="utf-8", errors="ignore")}

    @app.get("/api/registry/models")
    def list_registry_models(session: Session = Depends(get_session)) -> list[dict[str, object]]:
        items = session.exec(select(ModelArtifact).order_by(ModelArtifact.created_at.desc())).all()
        return [model_artifact_to_dict(item) for item in items]

    @app.post("/api/registry/models")
    def create_registry_model(payload: ModelArtifactCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        artifact = ModelArtifact(
            project_id=payload.project_id,
            name=payload.name,
            artifact_type=payload.artifact_type,
            source_pipeline=payload.source_pipeline,
            base_model=payload.base_model,
            storage_uri=payload.storage_uri,
            format=payload.format,
            benchmark_json=json.dumps(payload.benchmark, ensure_ascii=False),
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        return model_artifact_to_dict(artifact)

    @app.post("/api/registry/compare")
    def compare_registry_models(payload: RegistryCompareRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        baseline = session.get(ModelArtifact, payload.baseline_artifact_id)
        candidate = session.get(ModelArtifact, payload.candidate_artifact_id)
        if baseline is None or candidate is None:
            raise HTTPException(status_code=404, detail="Artefato baseline ou candidate nao encontrado.")
        baseline_scores = json.loads(baseline.benchmark_json or "{}")
        candidate_scores = json.loads(candidate.benchmark_json or "{}")
        delta: dict[str, float] = {}
        for key in sorted(set(baseline_scores) | set(candidate_scores)):
            try:
                delta[key] = float(candidate_scores.get(key, 0)) - float(baseline_scores.get(key, 0))
            except Exception:
                continue
        return {
            "baseline": model_artifact_to_dict(baseline),
            "candidate": model_artifact_to_dict(candidate),
            "delta": delta,
        }

    @app.post("/api/projects/{project_id}/deployments")
    def create_project_deployment(
        project_id: str,
        payload: DeploymentCreateRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Projeto nao encontrado.")
        artifact = session.get(ModelArtifact, payload.artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artefato nao encontrado.")
        deployment = ProjectDeployment(
            project_id=project_id,
            artifact_id=payload.artifact_id,
            environment=payload.environment,
            notes=payload.notes,
        )
        session.add(deployment)
        session.commit()
        return {
            "project_id": project_id,
            "artifact_id": payload.artifact_id,
            "environment": payload.environment,
            "notes": payload.notes,
            "created_at": utc_now().isoformat(),
        }

    @app.get("/{full_path:path}", response_model=None)
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Rota API nao encontrada.")
        requested_path = frontend_dist / full_path
        if requested_path.exists() and requested_path.is_file():
            return FileResponse(requested_path)
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend Orquestra ainda nao foi buildado.")

    return app


app = create_app()
