from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import AsyncIterator, Iterator

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
from .memory_candidates import MemoryCandidateExtractor
from .memory_graph import MemoryGraphService
from .memory_recall import MemoryRecallService, normalize_selector_mode
from .memory_types import default_memory_kind_for_scope, normalize_memory_kind
from .models import (
    ChatMessage,
    ChatSession,
    JobRecord,
    MemoryRecord,
    MemoryReviewCandidate,
    MemoryTopic,
    ModelArtifact,
    PlannerSnapshot,
    Project,
    ProjectDeployment,
    ProviderProfile,
    SessionTask,
    SessionSummary,
    SessionTranscript,
    TrainingCandidate,
    WorkflowRun,
    WorkspaceAsset,
    WorkspaceInsight,
    WorkspaceScan,
    utc_now,
)
from .operations import OrquestraOperations
from .planner import PlannerService
from .rag_memory import RagMemoryService
from .runtime_state import collect_runtime_state, resolve_app_version
from .services import (
    LocalRagEngine,
    RagQueryOptions,
    build_context_block,
    collect_legacy_rag_sources,
    compaction_state_to_dict,
    ensure_runtime_dirs,
    format_retrieved_sources,
    job_record_to_dict,
    list_gateway_providers,
    memory_review_candidate_to_dict,
    memory_record_to_dict,
    memory_topic_to_dict,
    model_artifact_to_dict,
    planner_snapshot_to_dict,
    project_to_dict,
    provider_profile_to_dict,
    session_task_to_dict,
    seed_default_state,
    session_summary_to_dict,
    workflow_run_to_dict,
    session_transcript_to_dict,
    training_candidate_to_dict,
    workspace_asset_to_dict,
    workspace_insight_to_dict,
    workspace_scan_to_dict,
)
from .session_profile import get_session_metadata, get_session_profile, profile_prompt_section, set_session_profile
from .workflow_engine import WorkflowEngine
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
    objective: str = ""
    preset: str = "assistant"
    memory_policy: dict[str, object] = Field(default_factory=dict)
    rag_policy: dict[str, object] = Field(default_factory=dict)
    persona_config: dict[str, object] = Field(default_factory=dict)


class SessionProfileRequest(BaseModel):
    objective: str = ""
    preset: str = "assistant"
    memory_policy: dict[str, object] = Field(default_factory=dict)
    rag_policy: dict[str, object] = Field(default_factory=dict)
    persona_config: dict[str, object] = Field(default_factory=dict)


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
    memory_enabled: bool | None = None
    memory_scopes: list[str] = Field(default_factory=list)
    include_workspace: bool | None = None
    include_sources: bool | None = None
    max_context_chars: int | None = None
    compaction_enabled: bool | None = None
    planner_enabled: bool | None = None
    task_context_enabled: bool | None = None
    memory_selector_mode: str | None = None
    context_budget: int | None = None


class MemoryUpsertRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    topic_id: str | None = None
    scope: str
    memory_kind: str | None = None
    source: str = "manual"
    content: str
    confidence: float = 0.5
    ttl_seconds: int | None = None
    approved_for_training: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class MemoryRecallRequest(BaseModel):
    query: str
    project_id: str | None = None
    session_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    memory_kinds: list[str] = Field(default_factory=list)
    limit: int = 6


class MemoryPromoteRequest(BaseModel):
    project_id: str | None = None
    scope: str = "project_memory"
    memory_kind: str | None = None
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


class MemoryCandidateReviewRequest(BaseModel):
    create_training_candidate: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class SessionTaskCreateRequest(BaseModel):
    subject: str
    description: str = ""
    active_form: str = ""
    status: str = "pending"
    owner: str = "orquestra"
    blocked_by: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    position: int | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class SessionTaskPatchRequest(BaseModel):
    subject: str | None = None
    description: str | None = None
    active_form: str | None = None
    status: str | None = None
    owner: str | None = None
    blocked_by: list[str] | None = None
    blocks: list[str] | None = None
    position: int | None = None
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
    memory_enabled: bool | None = None
    memory_scopes: list[str] = Field(default_factory=list)
    include_workspace: bool | None = None
    include_sources: bool | None = None
    max_context_chars: int | None = None
    compaction_enabled: bool | None = None
    planner_enabled: bool | None = None
    task_context_enabled: bool | None = None
    memory_selector_mode: str | None = None
    context_budget: int | None = None


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
    memory_kind: str | None = None
    source: str = "workspace"


class OperationRunRequest(BaseModel):
    action_id: str


class WorkflowStepRequest(BaseModel):
    step_type: str
    label: str = ""
    payload: dict[str, object] = Field(default_factory=dict)


class WorkflowRunCreateRequest(BaseModel):
    session_id: str | None = None
    task_id: str | None = None
    workflow_name: str
    summary: str = ""
    steps: list[WorkflowStepRequest] = Field(default_factory=list)


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


def _chat_session_to_dict(record: ChatSession) -> dict[str, object]:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "title": record.title,
        "provider_id": record.provider_id,
        "model_name": record.model_name,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "last_message_at": record.last_message_at.isoformat(),
        "status": record.status,
        "metadata": get_session_metadata(record),
        "profile": get_session_profile(record),
    }


def create_app(settings: OrquestraSettings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    app_version = resolve_app_version(app_settings.workspace_root)
    ensure_runtime_dirs(app_settings)
    engine = build_engine(app_settings.database_url)
    memory_graph = MemoryGraphService(app_settings)
    rag_memory = RagMemoryService(app_settings)
    memory_recall = MemoryRecallService(app_settings)
    planner = PlannerService()
    candidate_extractor = MemoryCandidateExtractor()
    workspace_service = WorkspaceService(app_settings)
    operations = OrquestraOperations(app_settings)
    workflows = WorkflowEngine(
        settings=app_settings,
        engine=engine,
        operations=operations,
        memory_graph=memory_graph,
        rag_memory=rag_memory,
        workspace_service=workspace_service,
    )

    def bootstrap_runtime() -> None:
        init_database(engine)
        with Session(engine) as session:
            seed_default_state(session, app_settings)
            workspace_service.gc_derivatives(session)
            session.commit()

    def shutdown_runtime() -> None:
        try:
            memory_graph.index.close()
        except Exception:
            pass
        try:
            workspace_service.index.close()
        except Exception:
            pass

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        bootstrap_runtime()
        try:
            yield
        finally:
            shutdown_runtime()

    app = FastAPI(
        title="Orquestra AI",
        version=app_version,
        description="Control plane unificado do Orquestra.",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.memory_graph = memory_graph
    app.state.rag_memory = rag_memory
    app.state.memory_recall = memory_recall
    app.state.planner = planner
    app.state.candidate_extractor = candidate_extractor
    app.state.workspace_service = workspace_service
    app.state.operations = operations
    app.state.workflows = workflows

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
        runtime_state = collect_runtime_state(app_settings)
        return {
            "ok": True,
            "app": "Orquestra AI",
            "app_version": app_version,
            "schema_version": runtime_state["schema_version"],
            "schema_target_version": runtime_state["target_schema_version"],
            "migration_required": runtime_state["migration_required"],
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
            "runtime": runtime_state,
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

    @app.get("/api/workflows/runs")
    def list_workflow_runs(session: Session = Depends(get_session)) -> list[dict[str, object]]:
        return workflows.list_runs(session)

    @app.get("/api/workflows/runs/{run_id}")
    def get_workflow_run(run_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            return workflows.get_run(session, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workflow não encontrado.") from exc

    @app.post("/api/workflows/runs")
    def create_workflow_run(payload: WorkflowRunCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        run_id = workflows.create_run(
            session_id=payload.session_id,
            task_id=payload.task_id,
            workflow_name=payload.workflow_name,
            summary=payload.summary,
            steps=[{"step_type": step.step_type, "label": step.label, **step.payload} for step in payload.steps],
        )
        session.expire_all()
        run = session.get(WorkflowRun, run_id)
        if run is None:
            raise HTTPException(status_code=500, detail="Workflow não pôde ser criado.")
        return workflow_run_to_dict(run)

    @app.post("/api/workflows/runs/{run_id}/cancel")
    def cancel_workflow_run(run_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            workflows.cancel_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workflow não encontrado.") from exc
        run = session.get(WorkflowRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Workflow não encontrado.")
        return workflow_run_to_dict(run)

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
        set_session_profile(
            record,
            objective=payload.objective,
            preset=payload.preset,
            memory_policy=payload.memory_policy,
            rag_policy=payload.rag_policy,
            persona_config=payload.persona_config,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return _chat_session_to_dict(record)

    @app.get("/api/chat/sessions")
    def list_chat_sessions(project_id: str | None = None, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        statement = select(ChatSession).order_by(ChatSession.updated_at.desc())
        if project_id:
            statement = statement.where(ChatSession.project_id == project_id)
        rows = session.exec(statement.limit(100)).all()
        return [_chat_session_to_dict(row) for row in rows]

    @app.get("/api/chat/sessions/{session_id}/profile")
    def get_chat_session_profile(session_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        return get_session_profile(chat_session)

    @app.put("/api/chat/sessions/{session_id}/profile")
    def update_chat_session_profile(
        session_id: str,
        payload: SessionProfileRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        profile = set_session_profile(
            chat_session,
            objective=payload.objective,
            preset=payload.preset,
            memory_policy=payload.memory_policy,
            rag_policy=payload.rag_policy,
            persona_config=payload.persona_config,
        )
        chat_session.updated_at = utc_now()
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return profile

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
        payload = session_summary_to_dict(summary)
        compaction_state = memory_graph.get_or_build_compaction_state(session, chat_session)
        snapshot = planner.get_snapshot(session, session_id)
        if snapshot is not None:
            next_steps = json.loads(snapshot.next_steps_json or "[]")
            payload["next_steps"] = "\n".join(f"- {item}" for item in next_steps)
            payload["planner"] = planner_snapshot_to_dict(snapshot)
        payload["compaction_state"] = compaction_state_to_dict(compaction_state)
        return payload

    @app.post("/api/chat/sessions/{session_id}/compact")
    def compact_chat_session(session_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        payload = memory_graph.compact_session(session, chat_session)
        session.commit()
        return payload

    @app.get("/api/chat/sessions/{session_id}/planner")
    def get_session_planner(session_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        summary = memory_graph.get_or_build_summary(session, chat_session)
        snapshot = planner.get_snapshot(session, session_id)
        if snapshot is None:
            snapshot, tasks = planner.rebuild_from_session(session, chat_session=chat_session, summary=summary)
            session.commit()
        else:
            tasks = planner.list_tasks(session, session_id)
        return {
            "snapshot": planner_snapshot_to_dict(snapshot),
            "tasks": [session_task_to_dict(task) for task in tasks],
        }

    @app.post("/api/chat/sessions/{session_id}/planner/rebuild")
    def rebuild_session_planner(session_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        summary = memory_graph.get_or_build_summary(session, chat_session)
        snapshot, tasks = planner.rebuild_from_session(session, chat_session=chat_session, summary=summary)
        session.commit()
        return {
            "snapshot": planner_snapshot_to_dict(snapshot),
            "tasks": [session_task_to_dict(task) for task in tasks],
        }

    @app.get("/api/chat/sessions/{session_id}/tasks")
    def list_session_tasks(session_id: str, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        return [session_task_to_dict(task) for task in planner.list_tasks(session, session_id)]

    @app.post("/api/chat/sessions/{session_id}/tasks")
    def create_session_task(
        session_id: str,
        payload: SessionTaskCreateRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        task = planner.create_task(
            session,
            session_id=session_id,
            subject=payload.subject,
            description=payload.description,
            active_form=payload.active_form,
            status=payload.status,
            owner=payload.owner,
            blocked_by=payload.blocked_by,
            blocks=payload.blocks,
            position=payload.position,
            metadata=payload.metadata,
        )
        session.commit()
        return session_task_to_dict(task)

    @app.patch("/api/chat/sessions/{session_id}/tasks")
    def patch_session_tasks(
        session_id: str,
        payload: SessionTaskPatchRequest,
        task_id: str = Query(...),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
        task = session.get(SessionTask, task_id)
        if task is None or task.session_id != session_id:
            raise HTTPException(status_code=404, detail="Tarefa nao encontrada.")
        updated = planner.update_task(
            session,
            task,
            subject=payload.subject,
            description=payload.description,
            active_form=payload.active_form,
            status=payload.status,
            owner=payload.owner,
            blocked_by=payload.blocked_by,
            blocks=payload.blocks,
            position=payload.position,
            metadata=payload.metadata or None,
        )
        session.commit()
        return session_task_to_dict(updated)

    @app.get("/api/tasks/{task_id}")
    def get_session_task(task_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        task = session.get(SessionTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Tarefa nao encontrada.")
        return session_task_to_dict(task)

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
            set_session_profile(chat_session, objective=payload.message[:180], preset="assistant")
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)
        else:
            provider_id = payload.provider_id or chat_session.provider_id or provider_id
            model_name = payload.model_name or chat_session.model_name or model_name

        summary = memory_graph.get_or_build_summary(session, chat_session)
        profile = get_session_profile(chat_session)
        memory_policy = profile.get("memory_policy", {})
        rag_policy = profile.get("rag_policy", {})
        effective_project_id = chat_session.project_id or payload.project_id
        memory_scopes = payload.memory_scopes or list(memory_policy.get("scopes", []))
        max_context_chars = payload.max_context_chars or int(rag_policy.get("max_context_chars", 9000) or 9000)
        planner_enabled = payload.planner_enabled if payload.planner_enabled is not None else True
        memory_enabled = (
            payload.memory_enabled
            if payload.memory_enabled is not None
            else bool(memory_policy.get("enabled", True) and rag_policy.get("include_memory", True))
        )
        include_workspace = payload.include_workspace if payload.include_workspace is not None else bool(rag_policy.get("include_workspace", True))
        include_sources = payload.include_sources if payload.include_sources is not None else bool(rag_policy.get("include_sources", True))
        selector_mode = normalize_selector_mode(payload.memory_selector_mode)
        context_snapshot = (
            memory_graph.build_context_snapshot(
                session,
                chat_session,
                context_budget=payload.context_budget or max_context_chars,
            )
            if payload.compaction_enabled is not False
            else {"context_text": summary.current_state, "compaction_state": {}}
        )
        planner_context = (
            planner.task_prompt_context(session, chat_session.id)
            if planner_enabled and payload.task_context_enabled is not False
            else ""
        )
        recall_result = {"items": [], "status": "disabled", "collection_name": "orquestra_memory_v1", "selector_mode": selector_mode}
        if memory_enabled:
            recall_result = memory_recall.recall(
                session,
                query=payload.message,
                project_id=effective_project_id,
                session_id=chat_session.id,
                scopes=memory_scopes,
                limit=int(rag_policy.get("top_k_memory", 6) or 6),
                selector_mode=selector_mode,
            )
        recalled = list(recall_result.get("items", []))
        snapshot_context = str(context_snapshot.get("context_text", summary.current_state)).strip()
        memory_context = memory_recall.format_context(recalled, max_chars=max(max_context_chars // 3, 1200))
        memory_citations = [
            {
                "channel": item.get("metadata", {}).get("channel", "memory") if isinstance(item.get("metadata"), dict) else "memory",
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "memory_kind": item.get("memory_kind", ""),
            }
            for item in recalled
        ]
        workspace_bundle = (
            workspace_service.build_context_snippet(
                session,
                project_id=effective_project_id,
                prompt=payload.message,
                include_sources=include_sources,
                limit=int(rag_policy.get("top_k_workspace", 4) or 4),
            )
            if include_workspace
            else {"items": [], "context": "", "citations": []}
        )
        workspace_context = str(workspace_bundle.get("context", "")).strip()
        workspace_citations = list(workspace_bundle.get("citations", []))
        legacy_sources = (
            collect_legacy_rag_sources(
                app_settings,
                question=payload.message,
                collection_names=list(rag_policy.get("collections", [])) or None,
                limit=int(rag_policy.get("top_k_sources", 4) or 4),
            )
            if include_sources
            else []
        )
        legacy_sources_context = format_retrieved_sources(legacy_sources, max_chars=max(max_context_chars // 3, 1200))
        prompt_context = build_context_block(
            [
                ("Perfil da sessão", profile_prompt_section(profile)),
                ("Snapshot compacto", snapshot_context),
                ("Planner ativo", planner_context if planner_enabled else ""),
                ("Memórias relevantes", memory_context),
                ("Workspace/fontes", workspace_context),
                ("RAG legado", legacy_sources_context),
            ],
            max_chars=max_context_chars,
        )
        contextual_citations = memory_citations + workspace_citations + legacy_sources

        gateway = OrquestraGateway(list_gateway_providers(session), mock=payload.mock_response)
        user_message = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content=payload.message,
            metadata_json=json.dumps(
                {
                    "session_profile": profile,
                    "rag_memory_recall": recall_result,
                    "recalled_memories": recalled,
                    "compaction_state": context_snapshot.get("compaction_state", {}),
                    "planner_enabled": planner_enabled,
                    "memory_selector_mode": selector_mode,
                    "include_workspace": include_workspace,
                    "include_sources": include_sources,
                    "workspace_context": workspace_bundle,
                    "legacy_sources": legacy_sources,
                },
                ensure_ascii=False,
            ),
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
                                prompt_context,
                                "Politica operacional: use memorias e RAG como apoio, mas nao promova nada para dataset sem aprovacao explicita.",
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
            metadata_json=json.dumps(
                {
                    "session_profile": profile,
                    "memory_recall": recalled,
                    "rag_memory_recall": recall_result,
                    "citations": contextual_citations,
                    "compaction_state": context_snapshot.get("compaction_state", {}),
                    "workspace_context": workspace_bundle,
                    "legacy_sources": legacy_sources,
                    "memory_selector_mode": selector_mode,
                },
                ensure_ascii=False,
            ),
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
        planner_snapshot = planner.get_snapshot(session, chat_session.id)
        planner_tasks = planner.list_tasks(session, chat_session.id)
        if planner_enabled:
            planner_snapshot, planner_tasks = planner.rebuild_from_session(session, chat_session=chat_session, summary=updated_summary)
        candidates = candidate_extractor.extract_from_chat_turn(
            session,
            chat_session=chat_session,
            profile=profile,
            user_message=user_message,
            assistant_message=assistant_message,
            citations=contextual_citations,
            recalled=recalled,
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
                    "next_steps": (
                        "\n".join(f"- {item}" for item in json.loads(planner_snapshot.next_steps_json or "[]"))
                        if planner_snapshot is not None
                        else str(json.loads(updated_summary.sections_json or "{}").get("next_steps", ""))
                    ),
                    "updated_at": updated_summary.updated_at.isoformat(),
                    "planner_task_count": len(planner_tasks),
                },
            )
            yield _sse(
                "done",
                {
                    "provider_id": response.provider_id,
                    "model_name": response.model_name,
                    "usage": response.usage,
                    "latency_seconds": response.latency_seconds,
                    "memory_candidates_created": len(candidates),
                    "memory_recall_count": len(recalled),
                    "workspace_context_count": len(workspace_bundle.get("items", [])),
                    "legacy_source_count": len(legacy_sources),
                },
            )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/api/memory")
    def list_memory(
        project_id: str | None = None,
        scope: str | None = None,
        memory_kind: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        statement = select(MemoryRecord).order_by(MemoryRecord.created_at.desc())
        if project_id:
            statement = statement.where(MemoryRecord.project_id == project_id)
        if scope:
            statement = statement.where(MemoryRecord.scope == scope)
        if memory_kind:
            statement = statement.where(MemoryRecord.memory_kind == normalize_memory_kind(memory_kind))
        rows = session.exec(statement.limit(120)).all()
        return [memory_record_to_dict(row) for row in rows]

    @app.post("/api/memory/upsert")
    def upsert_memory(payload: MemoryUpsertRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        record = MemoryRecord(
            project_id=payload.project_id,
            session_id=payload.session_id,
            topic_id=payload.topic_id,
            scope=payload.scope,
            memory_kind=normalize_memory_kind(payload.memory_kind, default=default_memory_kind_for_scope(payload.scope)),
            source=payload.source,
            content=payload.content,
            confidence=payload.confidence,
            ttl_seconds=payload.ttl_seconds,
            approved_for_training=payload.approved_for_training,
            metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
        )
        session.add(record)
        session.flush()
        projection_result = memory_graph.project_memory_record(
            session,
            record,
            title=str(payload.metadata.get("title", payload.source)),
            metadata=payload.metadata,
        )
        session.commit()
        session.refresh(record)
        index_result = rag_memory.upsert_memory(
            record,
            title=str(payload.metadata.get("title", payload.source)),
            preset=str(payload.metadata.get("preset", "")),
            source_kind="manual_memory",
            approved=True,
        )
        payload_dict = memory_record_to_dict(record)
        payload_dict["rag_index"] = index_result
        payload_dict["projection"] = projection_result
        return payload_dict

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
        result = memory_recall.recall(
            session,
            query=payload.query,
            project_id=payload.project_id,
            session_id=payload.session_id,
            scopes=payload.scopes,
            memory_kinds=payload.memory_kinds,
            limit=payload.limit,
        )
        return {"query": payload.query, **result}

    @app.post("/api/memory/promote")
    def promote_memory(payload: MemoryPromoteRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        topic, _, record = memory_graph.promote_to_topic(
            session,
            project_id=payload.project_id,
            scope=payload.scope,
            memory_kind=payload.memory_kind,
            title=payload.title,
            content=payload.content,
            source=payload.source,
            metadata=payload.metadata,
        )
        session.commit()
        session.refresh(topic)
        session.refresh(record)
        index_result = rag_memory.upsert_memory(
            record,
            title=payload.title,
            preset=str(payload.metadata.get("preset", "")),
            source_kind="memory_topic",
            source_ref=topic.id,
            approved=True,
        )
        return {
            "topic": memory_topic_to_dict(topic),
            "record": memory_record_to_dict(record),
            "rag_index": index_result,
        }

    @app.get("/api/memory/candidates")
    def list_memory_review_candidates(
        project_id: str | None = None,
        session_id: str | None = None,
        status: str | None = "pending",
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        statement = select(MemoryReviewCandidate).order_by(MemoryReviewCandidate.created_at.desc())
        if project_id:
            statement = statement.where(MemoryReviewCandidate.project_id == project_id)
        if session_id:
            statement = statement.where(MemoryReviewCandidate.session_id == session_id)
        if status:
            statement = statement.where(MemoryReviewCandidate.status == status)
        rows = session.exec(statement.limit(160)).all()
        return [memory_review_candidate_to_dict(row) for row in rows]

    @app.post("/api/memory/candidates/{candidate_id}/approve")
    def approve_memory_review_candidate(
        candidate_id: str,
        payload: MemoryCandidateReviewRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        candidate = session.get(MemoryReviewCandidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidato de memoria nao encontrado.")
        if candidate.status != "pending":
            raise HTTPException(status_code=409, detail="Candidato ja revisado.")

        metadata = json.loads(candidate.metadata_json or "{}")
        review_metadata = metadata | payload.metadata | {"approved_at": utc_now().isoformat(), "title": candidate.title}
        record = MemoryRecord(
            project_id=candidate.project_id,
            session_id=candidate.session_id,
            scope=candidate.scope,
            memory_kind=candidate.memory_kind,
            source=f"memory_candidate:{candidate.id}",
            content=candidate.content,
            confidence=candidate.confidence,
            approved_for_training=payload.create_training_candidate,
            metadata_json=json.dumps(review_metadata, ensure_ascii=False),
        )
        session.add(record)
        candidate.status = "approved"
        candidate.reviewed_at = utc_now()
        candidate.metadata_json = json.dumps(review_metadata, ensure_ascii=False)
        session.add(candidate)
        session.flush()
        projection_result = memory_graph.project_memory_record(session, record, title=candidate.title, metadata=review_metadata)
        index_result = rag_memory.upsert_memory(
            record,
            title=candidate.title,
            preset=str(metadata.get("preset", "")),
            source_kind="memory_candidate",
            source_ref=candidate.id,
            approved=True,
        )

        training_record = None
        if payload.create_training_candidate:
            source_ids = json.loads(candidate.source_message_ids_json or "[]")
            source_messages = [session.get(ChatMessage, item) for item in source_ids]
            user_turn = next((item for item in source_messages if item is not None and item.role == "user"), None)
            assistant_turn = next((item for item in source_messages if item is not None and item.role == "assistant"), None)
            training_record = memory_graph.create_training_candidate(
                session,
                project_id=candidate.project_id,
                session_id=candidate.session_id,
                source=f"memory_candidate:{candidate.id}",
                instruction=user_turn.content if user_turn else candidate.title,
                context=candidate.rationale,
                response=assistant_turn.content if assistant_turn else candidate.content,
                labels={
                    "preset": metadata.get("preset"),
                    "scope": candidate.scope,
                    "explicitly_approved": True,
                },
                approved=False,
                metadata={
                    "memory_candidate_id": candidate.id,
                    "memory_record_id": record.id,
                    "citations": json.loads(candidate.citations_json or "[]"),
                },
            )

        session.commit()
        session.refresh(candidate)
        session.refresh(record)
        return {
            "candidate": memory_review_candidate_to_dict(candidate),
            "record": memory_record_to_dict(record),
            "training_candidate": training_candidate_to_dict(training_record) if training_record else None,
            "rag_index": index_result,
            "projection": projection_result,
        }

    @app.post("/api/memory/candidates/{candidate_id}/reject")
    def reject_memory_review_candidate(
        candidate_id: str,
        payload: MemoryCandidateReviewRequest | None = None,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        candidate = session.get(MemoryReviewCandidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidato de memoria nao encontrado.")
        if candidate.status != "pending":
            raise HTTPException(status_code=409, detail="Candidato ja revisado.")
        metadata = json.loads(candidate.metadata_json or "{}")
        candidate.status = "rejected"
        candidate.reviewed_at = utc_now()
        candidate.metadata_json = json.dumps(metadata | ((payload.metadata if payload else {}) or {}) | {"rejected_at": utc_now().isoformat()}, ensure_ascii=False)
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        return memory_review_candidate_to_dict(candidate)

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
                memory_enabled=payload.memory_enabled if payload.memory_enabled is not None else True,
                memory_scopes=payload.memory_scopes or None,
                include_workspace=payload.include_workspace if payload.include_workspace is not None else True,
                include_sources=payload.include_sources if payload.include_sources is not None else True,
                max_context_chars=payload.max_context_chars or 9000,
                compaction_enabled=payload.compaction_enabled if payload.compaction_enabled is not None else True,
                planner_enabled=payload.planner_enabled if payload.planner_enabled is not None else True,
                task_context_enabled=payload.task_context_enabled if payload.task_context_enabled is not None else True,
                memory_selector_mode=payload.memory_selector_mode or "hybrid",
                context_budget=payload.context_budget,
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
        if payload.memory_kind:
            record.memory_kind = normalize_memory_kind(payload.memory_kind, default=record.memory_kind)
        session.flush()
        projection_result = memory_graph.project_memory_record(
            session,
            record,
            title=asset.title or asset.relative_path,
            metadata=json.loads(record.metadata_json or "{}"),
        )
        session.commit()
        session.refresh(record)
        payload_dict = memory_record_to_dict(record)
        payload_dict["rag_index"] = rag_memory.upsert_memory(
            record,
            title=asset.title or asset.relative_path,
            source_kind="workspace_asset",
            source_ref=asset.id,
            approved=True,
        )
        payload_dict["projection"] = projection_result
        return payload_dict

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
