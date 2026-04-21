from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
from typing import AsyncIterator, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

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
    OsintClaim,
    OsintConnectorConfig,
    OsintEvidence,
    OsintInvestigation,
    OsintSourceRegistryEntry,
    PlannerSnapshot,
    Project,
    ProjectDeployment,
    ProviderProfile,
    RemoteTrainPlaneConfig,
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
from .osint import OsintService, get_osint_config, save_osint_config, seed_osint_state
from .session_profile import get_session_metadata, get_session_profile, profile_prompt_section, set_session_profile
from .trainplane import (
    TrainPlaneClientError,
    build_dataset_bundle_records,
    build_trainplane_client,
    get_or_create_trainplane_config,
    get_trainplane_token,
    mirror_remote_artifact,
    mirror_remote_run,
    set_trainplane_token,
    trainplane_config_to_dict,
)
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
    investigation_id: str | None = None
    osint_mode: bool | None = None
    fresh_web_enabled: bool | None = None
    evidence_enabled: bool | None = None
    source_registry_ids: list[str] = Field(default_factory=list)
    enabled_connector_ids: list[str] = Field(default_factory=list)
    via_tor: bool | None = None


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
    include_osint_evidence: bool | None = None
    investigation_id: str | None = None
    claim_status: str | None = None
    evidence_budget: int | None = None
    fresh_web_enabled: bool | None = None
    source_registry_ids: list[str] = Field(default_factory=list)
    enabled_connector_ids: list[str] = Field(default_factory=list)
    via_tor: bool | None = None


class OsintConfigRequest(BaseModel):
    search_timeout_seconds: int | None = None
    fetch_timeout_seconds: int | None = None
    default_max_results: int | None = None
    default_fetch_limit: int | None = None
    default_evidence_limit: int | None = None
    tor_proxy_url: str | None = None
    store_result_metadata: bool | None = None
    store_full_provider_snippet: bool | None = None


class OsintConnectorPatchRequest(BaseModel):
    enabled_global: bool | None = None
    enabled_by_default: bool | None = None
    priority: int | None = None
    training_allowed: bool | None = None
    retention_policy: str | None = None
    via_tor_allowed: bool | None = None
    health_status: str | None = None
    project_overrides: dict[str, object] | None = None
    metadata: dict[str, object] | None = None


class OsintSourceRegistryEntryRequest(BaseModel):
    source_key: str
    connector_id: str | None = None
    title: str
    category: str = "manual_seed"
    access_type: str = "web"
    base_url: str = ""
    description: str = ""
    retention_policy: str = "metadata_only"
    training_allowed: bool = False
    reliability: float = 0.5
    jurisdiction_tags: list[str] = Field(default_factory=list)
    preset_tags: list[str] = Field(default_factory=list)
    tor_supported: bool = False
    api_auth_required: bool = False
    robots_sensitive: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class OsintInvestigationCreateRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    title: str
    objective: str = ""
    target_entity: str = ""
    language: str = "pt-BR"
    jurisdiction: str = "global"
    mode: str = "balanced"
    enabled_connector_ids: list[str] = Field(default_factory=list)
    source_registry_ids: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class OsintInvestigationPatchRequest(BaseModel):
    title: str | None = None
    objective: str | None = None
    target_entity: str | None = None
    language: str | None = None
    jurisdiction: str | None = None
    mode: str | None = None
    status: str | None = None
    enabled_connector_ids: list[str] | None = None
    source_registry_ids: list[str] | None = None
    allowed_domains: list[str] | None = None
    blocked_domains: list[str] | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class OsintPlanRequest(BaseModel):
    query: str | None = None


class OsintSearchRequest(BaseModel):
    query: str
    connector_ids: list[str] = Field(default_factory=list)
    source_registry_ids: list[str] = Field(default_factory=list)
    via_tor: bool = False
    limit: int | None = None


class OsintFetchRequest(BaseModel):
    source_id: str | None = None
    url: str | None = None
    via_tor: bool = False
    follow_same_host_redirects_only: bool = False


class OsintCrawlRequest(BaseModel):
    source_ids: list[str] = Field(default_factory=list)
    via_tor: bool = False
    follow_same_host_redirects_only: bool = False


class OsintClaimApproveRequest(BaseModel):
    create_memory: bool = True


class OsintExportRequest(BaseModel):
    investigation_id: str


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


class RemoteTrainPlaneConfigRequest(BaseModel):
    base_url: str = ""
    token: str | None = None
    region: str = ""
    instance_id: str = ""
    bucket: str = ""
    ssm_enabled: bool = True
    default_training_profile: dict[str, object] = Field(default_factory=dict)
    default_serving_profile: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)


class RemoteTrainPlaneBaseModelSyncRequest(BaseModel):
    project_id: str | None = None
    name: str
    source_kind: str = "huggingface_ref"
    source_ref: str = ""
    local_path: str = ""
    format: str = "huggingface"
    metadata: dict[str, object] = Field(default_factory=dict)


class RemoteTrainPlaneDatasetSyncRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    project_slug: str = ""
    name: str = "dataset-bundle"
    approved_only: bool = True
    max_records: int = 200
    metadata: dict[str, object] = Field(default_factory=dict)


class RemoteTrainPlaneRunCreateRequest(BaseModel):
    project_id: str | None = None
    project_slug: str = ""
    name: str
    base_model_id: str
    dataset_bundle_id: str
    summary: str = ""
    training_profile: dict[str, object] = Field(default_factory=dict)


class RemoteTrainPlaneEvaluationRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    candidate_artifact_id: str
    baseline_mode: str
    baseline_ref: str = ""
    baseline_provider_id: str | None = None
    baseline_model_name: str | None = None
    suite_name: str = "default-suite"
    prompts: list[str] = Field(default_factory=list)
    cases: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class RemoteTrainPlaneComparisonRequest(BaseModel):
    project_id: str | None = None
    session_id: str | None = None
    candidate_artifact_id: str
    baseline_mode: str
    baseline_ref: str = ""
    baseline_provider_id: str | None = None
    baseline_model_name: str | None = None
    prompt_set_name: str = "default-compare"
    prompts: list[str] = Field(default_factory=list)
    cases: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


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
    osint_service = OsintService(app_settings)
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
            seed_osint_state(session)
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
    app.state.osint_service = osint_service
    app.state.planner = planner
    app.state.candidate_extractor = candidate_extractor
    app.state.workspace_service = workspace_service
    app.state.operations = operations
    app.state.workflows = workflows
    app.state.trainplane_client_builder = build_trainplane_client

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

    def get_trainplane_client(session: Session = Depends(get_session)):
        return app.state.trainplane_client_builder(session)

    def trainplane_config_payload(session: Session) -> dict[str, object]:
        config = get_or_create_trainplane_config(session)
        return trainplane_config_to_dict(config, token_configured=bool(get_trainplane_token()))

    def build_prompt_cases(prompts: list[str], cases: list[dict[str, object]]) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for raw_case in cases:
            prompt = str(raw_case.get("prompt", "")).strip()
            if not prompt:
                continue
            normalized.append(
                {
                    "prompt": prompt,
                    "expected_output": str(raw_case.get("expected_output", "")).strip(),
                    "baseline_output": str(raw_case.get("baseline_output", "")).strip(),
                    "metadata": raw_case.get("metadata", {}) if isinstance(raw_case.get("metadata"), dict) else {},
                }
            )
        for prompt in prompts:
            text = prompt.strip()
            if text:
                normalized.append({"prompt": text, "expected_output": "", "baseline_output": "", "metadata": {}})
        deduped: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in normalized:
            key = item["prompt"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def complete_local_baseline_cases(
        *,
        session: Session,
        baseline_mode: str,
        baseline_provider_id: str | None,
        baseline_model_name: str | None,
        cases: list[dict[str, object]],
    ) -> tuple[list[dict[str, object]], str]:
        resolved_ref = ""
        if baseline_mode not in {"lmstudio_local", "provider_api"}:
            return cases, resolved_ref
        provider_id = baseline_provider_id or ("lmstudio" if baseline_mode == "lmstudio_local" else app_settings.default_provider_id)
        gateway = OrquestraGateway(list_gateway_providers(session))
        resolved_model = baseline_model_name or None
        for item in cases:
            if item.get("baseline_output"):
                continue
            try:
                response = gateway.generate(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Voce responde como baseline operacional do Orquestra. "
                                "Seja direto, objetivo e preserve continuidade de contexto quando existir."
                            ),
                        },
                        {"role": "user", "content": str(item.get("prompt", ""))},
                    ],
                    provider_id=provider_id,
                    model_name=resolved_model,
                    temperature=0.1,
                    max_tokens=500,
                )
            except GatewayLlmError as exc:
                raise HTTPException(status_code=502, detail=f"Falha ao consultar baseline local {provider_id}: {exc}") from exc
            item["baseline_output"] = response.content
            resolved_model = response.model_name
        return cases, f"{provider_id}/{resolved_model or 'default'}"

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

    @app.get("/api/osint/config")
    def get_osint_runtime_config(session: Session = Depends(get_session)) -> dict[str, object]:
        return get_osint_config(session)

    @app.put("/api/osint/config")
    def update_osint_runtime_config(payload: OsintConfigRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        updates = payload.model_dump(exclude_none=True)
        config = save_osint_config(session, updates)
        session.commit()
        return config

    @app.get("/api/osint/providers")
    def list_osint_providers(
        project_id: str | None = None,
        investigation_id: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        connectors = osint_service.list_connectors(session, project_id=project_id, investigation_id=investigation_id)
        return [item for item in connectors if item.get("category") == "search_provider"]

    @app.get("/api/osint/connectors")
    def list_osint_connectors(
        project_id: str | None = None,
        investigation_id: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        return osint_service.list_connectors(session, project_id=project_id, investigation_id=investigation_id)

    @app.patch("/api/osint/connectors/{connector_id}")
    def patch_osint_connector(
        connector_id: str,
        payload: OsintConnectorPatchRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            updated = osint_service.update_connector(session, connector_id, **payload.model_dump(exclude_none=True))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Conector OSINT não encontrado.") from exc
        session.commit()
        return updated

    @app.post("/api/osint/connectors/{connector_id}/enable")
    def enable_osint_connector(connector_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            updated = osint_service.update_connector(session, connector_id, enabled_global=True)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Conector OSINT não encontrado.") from exc
        session.commit()
        return updated

    @app.post("/api/osint/connectors/{connector_id}/disable")
    def disable_osint_connector(connector_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            updated = osint_service.update_connector(session, connector_id, enabled_global=False)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Conector OSINT não encontrado.") from exc
        session.commit()
        return updated

    @app.get("/api/osint/source-registry")
    def list_osint_source_registry(session: Session = Depends(get_session)) -> list[dict[str, object]]:
        return osint_service.list_registry(session)

    @app.post("/api/osint/source-registry")
    def create_osint_source_registry_entry(
        payload: OsintSourceRegistryEntryRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            item = osint_service.upsert_registry_entry(session, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session.commit()
        return item

    @app.patch("/api/osint/source-registry/{entry_id}")
    def patch_osint_source_registry_entry(
        entry_id: str,
        payload: OsintSourceRegistryEntryRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        row = session.get(OsintSourceRegistryEntry, entry_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Fonte do registry OSINT não encontrada.")
        merged = payload.model_dump()
        merged["source_key"] = row.source_key
        item = osint_service.upsert_registry_entry(session, merged)
        session.commit()
        return item

    @app.get("/api/osint/investigations")
    def list_osint_investigations(
        project_id: str | None = None,
        session_id: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        return osint_service.list_investigations(session, project_id=project_id, session_id=session_id)

    @app.post("/api/osint/investigations")
    def create_osint_investigation(
        payload: OsintInvestigationCreateRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        investigation = osint_service.create_investigation(session, **payload.model_dump())
        session.commit()
        return investigation

    @app.get("/api/osint/investigations/{investigation_id}")
    def get_osint_investigation(investigation_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        row = session.get(OsintInvestigation, investigation_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Investigação OSINT não encontrada.")
        return osint_service.investigation_to_dict(row)

    @app.patch("/api/osint/investigations/{investigation_id}")
    def patch_osint_investigation(
        investigation_id: str,
        payload: OsintInvestigationPatchRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            investigation = osint_service.update_investigation(session, investigation_id, payload.model_dump(exclude_unset=True))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Investigação OSINT não encontrada.") from exc
        session.commit()
        return investigation

    @app.post("/api/osint/investigations/{investigation_id}/plan")
    def plan_osint_investigation(
        investigation_id: str,
        payload: OsintPlanRequest | None = None,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            planned = osint_service.plan_queries(session, investigation_id, query=payload.query if payload else None)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Investigação OSINT não encontrada.") from exc
        session.commit()
        return planned

    @app.post("/api/osint/investigations/{investigation_id}/search")
    def search_osint_investigation(
        investigation_id: str,
        payload: OsintSearchRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            result = osint_service.search(
                session,
                investigation_id=investigation_id,
                query=payload.query,
                connector_ids=payload.connector_ids,
                source_registry_ids=payload.source_registry_ids,
                via_tor=payload.via_tor,
                limit=payload.limit,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Investigação OSINT não encontrada.") from exc
        session.commit()
        return result

    @app.post("/api/osint/investigations/{investigation_id}/fetch")
    def fetch_osint_investigation(
        investigation_id: str,
        payload: OsintFetchRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            result = osint_service.fetch(
                session,
                investigation_id=investigation_id,
                source_id=payload.source_id,
                url=payload.url,
                via_tor=payload.via_tor,
                follow_same_host_redirects_only=payload.follow_same_host_redirects_only,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Investigação OSINT não encontrada.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session.commit()
        return result

    @app.post("/api/osint/investigations/{investigation_id}/crawl")
    def crawl_osint_investigation(
        investigation_id: str,
        payload: OsintCrawlRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        results: list[dict[str, object]] = []
        for source_id in payload.source_ids:
            try:
                results.append(
                    osint_service.fetch(
                        session,
                        investigation_id=investigation_id,
                        source_id=source_id,
                        via_tor=payload.via_tor,
                        follow_same_host_redirects_only=payload.follow_same_host_redirects_only,
                    )
                )
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Investigação OSINT não encontrada.") from exc
        session.commit()
        return {"investigation_id": investigation_id, "fetches": results, "count": len(results)}

    @app.get("/api/osint/investigations/{investigation_id}/runs")
    def list_osint_runs(investigation_id: str, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        return osint_service.list_runs(session, investigation_id)

    @app.get("/api/osint/evidence")
    def list_osint_evidence(
        investigation_id: str | None = None,
        validation_status: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        return osint_service.list_evidence(session, investigation_id=investigation_id, validation_status=validation_status)

    @app.post("/api/osint/evidence/{evidence_id}/approve")
    def approve_osint_evidence(evidence_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            payload = osint_service.approve_evidence(session, evidence_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Evidência OSINT não encontrada.") from exc
        session.commit()
        return payload

    @app.get("/api/osint/claims")
    def list_osint_claims(
        investigation_id: str | None = None,
        status: str | None = None,
        session: Session = Depends(get_session),
    ) -> list[dict[str, object]]:
        return osint_service.list_claims(session, investigation_id=investigation_id, status=status)

    @app.post("/api/osint/claims/{claim_id}/approve")
    def approve_osint_claim(
        claim_id: str,
        payload: OsintClaimApproveRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            result = osint_service.approve_claim(session, claim_id, create_memory=payload.create_memory)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Claim OSINT não encontrada.") from exc
        projection = None
        rag_index = None
        memory_record_payload = result.get("memory_record")
        if isinstance(memory_record_payload, dict):
            memory_record = session.get(MemoryRecord, memory_record_payload.get("id"))
            claim = session.get(OsintClaim, claim_id)
            if memory_record is not None and claim is not None:
                projection = memory_graph.project_memory_record(
                    session,
                    memory_record,
                    title=str(memory_record_payload.get("metadata", {}).get("title", memory_record.source)),
                    metadata=memory_record_payload.get("metadata", {}),
                )
                rag_index = rag_memory.upsert_memory(
                    memory_record,
                    title=str(memory_record_payload.get("metadata", {}).get("title", memory_record.source)),
                    preset="osint",
                    source_kind="osint_claim",
                    source_ref=claim.id,
                    approved=True,
                )
        session.commit()
        return {**result, "projection": projection, "rag_index": rag_index}

    @app.post("/api/osint/export/dataset-bundle")
    def export_osint_dataset_bundle(
        payload: OsintExportRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        try:
            result = osint_service.export_dataset_bundle(session, investigation_id=payload.investigation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Investigação OSINT não encontrada.") from exc
        session.commit()
        return result

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
            set_session_profile(
                chat_session,
                objective=payload.message[:180],
                preset="osint" if payload.osint_mode else "assistant",
            )
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
        osint_mode = payload.osint_mode if payload.osint_mode is not None else profile.get("preset") == "osint"
        evidence_enabled = payload.evidence_enabled if payload.evidence_enabled is not None else osint_mode
        fresh_web_enabled = payload.fresh_web_enabled if payload.fresh_web_enabled is not None else False
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
        osint_bundle = (
            osint_service.build_context_bundle(
                session,
                query=payload.message,
                project_id=effective_project_id,
                session_id=chat_session.id,
                investigation_id=payload.investigation_id,
                fresh_web_enabled=fresh_web_enabled,
                evidence_enabled=evidence_enabled,
                enabled_connector_ids=payload.enabled_connector_ids or None,
                source_registry_ids=payload.source_registry_ids or None,
                via_tor=bool(payload.via_tor),
                limit=max(1, int(rag_policy.get("top_k_sources", 4) or 4)),
            )
            if (evidence_enabled or fresh_web_enabled)
            else {"context": "", "citations": [], "evidence": [], "fresh_results": [], "status": "disabled"}
        )
        osint_context = str(osint_bundle.get("context", "")).strip()
        osint_citations = list(osint_bundle.get("citations", []))
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
                ("OSINT evidence", osint_context),
                ("Workspace/fontes", workspace_context),
                ("RAG legado", legacy_sources_context),
            ],
            max_chars=max_context_chars,
        )
        contextual_citations = memory_citations + osint_citations + workspace_citations + legacy_sources

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
                    "osint_mode": osint_mode,
                    "evidence_enabled": evidence_enabled,
                    "fresh_web_enabled": fresh_web_enabled,
                    "osint_bundle": osint_bundle,
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
                    "osint_bundle": osint_bundle,
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
                    "osint_evidence_count": len(osint_bundle.get("evidence", [])),
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
        citations = json.loads(candidate.citations_json or "[]")
        source_message_ids = json.loads(candidate.source_message_ids_json or "[]")
        first_citation = citations[0] if citations and isinstance(citations[0], dict) else {}
        review_metadata = metadata | payload.metadata | {
            "approved_at": utc_now().isoformat(),
            "title": candidate.title,
            "citations": citations,
            "source_message_ids": source_message_ids,
            "source_url": first_citation.get("source") or first_citation.get("url") or metadata.get("source_url", ""),
            "validation_status": "approved",
        }
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
            source_ids = source_message_ids
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
                    "citations": citations,
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
        chat_session = session.get(ChatSession, payload.session_id) if payload.session_id else None
        session_profile = get_session_profile(chat_session) if chat_session is not None else {}
        include_osint_default = session_profile.get("preset") == "osint"
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
                include_osint_evidence=payload.include_osint_evidence if payload.include_osint_evidence is not None else include_osint_default,
                investigation_id=payload.investigation_id,
                evidence_budget=payload.evidence_budget or 4,
                fresh_web_enabled=payload.fresh_web_enabled if payload.fresh_web_enabled is not None else False,
                source_registry_ids=payload.source_registry_ids or None,
                enabled_connector_ids=payload.enabled_connector_ids or None,
                via_tor=bool(payload.via_tor),
            ),
            project_id=payload.project_id,
        )
        session.commit()
        return JSONResponse(result)

    @app.get("/api/remote/trainplane/config")
    def get_remote_trainplane_config(session: Session = Depends(get_session)) -> dict[str, object]:
        return trainplane_config_payload(session)

    @app.put("/api/remote/trainplane/config")
    def update_remote_trainplane_config(
        payload: RemoteTrainPlaneConfigRequest,
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        config = get_or_create_trainplane_config(session)
        config.base_url = payload.base_url.strip()
        config.region = payload.region.strip()
        config.instance_id = payload.instance_id.strip()
        config.bucket = payload.bucket.strip()
        config.ssm_enabled = payload.ssm_enabled
        config.default_training_profile_json = json.dumps(payload.default_training_profile, ensure_ascii=False)
        config.default_serving_profile_json = json.dumps(payload.default_serving_profile, ensure_ascii=False)
        config.metadata_json = json.dumps(payload.metadata, ensure_ascii=False)
        config.updated_at = utc_now()
        session.add(config)
        if payload.token is not None:
            try:
                set_trainplane_token(payload.token)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Falha ao salvar token do Train Plane: {exc}") from exc
        session.commit()
        session.refresh(config)
        return trainplane_config_payload(session)

    @app.post("/api/remote/trainplane/test-connection")
    def test_remote_trainplane_connection(
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        config_payload = trainplane_config_payload(session)
        try:
            health_payload = client.health()
        except TrainPlaneClientError as exc:
            return {"ok": False, "config": config_payload, "error": str(exc)}
        return {"ok": True, "config": config_payload, "health": health_payload}

    @app.get("/api/remote/trainplane/base-models")
    def list_remote_trainplane_base_models(client=Depends(get_trainplane_client)) -> list[dict[str, object]]:
        try:
            return client.list_base_models()
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/remote/trainplane/sync/base-model")
    def sync_remote_trainplane_base_model(
        payload: RemoteTrainPlaneBaseModelSyncRequest,
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        size_bytes = 0
        checksum_sha256 = ""
        storage_uri = payload.source_ref.strip()
        if payload.local_path.strip():
            local_path = Path(payload.local_path).expanduser()
            if not local_path.exists():
                raise HTTPException(status_code=404, detail="Arquivo local do base model não encontrado.")
            size_bytes = local_path.stat().st_size
            digest = hashlib.sha256()
            with local_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            checksum_sha256 = digest.hexdigest()
            storage_uri = f"file://{local_path.resolve()}"
        try:
            init_payload = client.init_base_model_upload(
                {
                    "name": payload.name,
                    "source_kind": payload.source_kind,
                    "source_ref": payload.source_ref,
                    "size_bytes": size_bytes,
                    "checksum_sha256": checksum_sha256,
                    "format": payload.format,
                    "metadata": {
                        **payload.metadata,
                        "project_id": payload.project_id,
                        "local_path": payload.local_path,
                    },
                }
            )
            return client.complete_base_model_upload(
                {
                    "upload_id": str(init_payload.get("upload_id", "")),
                    "storage_uri": storage_uri or f"orquestra://base-models/{payload.name}",
                    "metadata": {"synced_from": "orquestra_local"},
                }
            )
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/remote/trainplane/dataset-bundles")
    def list_remote_trainplane_dataset_bundles(client=Depends(get_trainplane_client)) -> list[dict[str, object]]:
        try:
            return client.list_dataset_bundles()
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/remote/trainplane/sync/dataset-bundle")
    def sync_remote_trainplane_dataset_bundle(
        payload: RemoteTrainPlaneDatasetSyncRequest,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        records = build_dataset_bundle_records(
            session,
            project_id=payload.project_id,
            session_id=payload.session_id,
            approved_only=payload.approved_only,
            max_records=payload.max_records,
        )
        if not records:
            raise HTTPException(status_code=400, detail="Nenhum training candidate disponível para exportar.")
        project_slug = payload.project_slug.strip()
        if not project_slug and payload.project_id:
            project = session.get(Project, payload.project_id)
            project_slug = project.slug if project is not None else ""
        project_slug = project_slug or app_settings.default_project_slug
        try:
            return client.create_dataset_bundle(
                {
                    "project_slug": project_slug,
                    "name": payload.name,
                    "source": "orquestra_local",
                    "records": records,
                    "metadata": {
                        **payload.metadata,
                        "project_id": payload.project_id,
                        "session_id": payload.session_id,
                        "approved_only": payload.approved_only,
                    },
                }
            )
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/remote/trainplane/runs")
    def list_remote_trainplane_runs(
        project_id: str | None = None,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> list[dict[str, object]]:
        try:
            payload = client.list_runs()
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        results: list[dict[str, object]] = []
        for item in payload:
            mirrored = mirror_remote_run(session, item, project_id=project_id)
            enriched = {**item, "mirrored_job_id": mirrored.id}
            results.append(enriched)
        artifact_payload = client.list_artifacts()
        for artifact in artifact_payload:
            mirror_remote_artifact(session, artifact, project_id=project_id)
        session.commit()
        return results

    @app.post("/api/remote/trainplane/runs")
    def create_remote_trainplane_run(
        payload: RemoteTrainPlaneRunCreateRequest,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        project_slug = payload.project_slug.strip()
        if not project_slug and payload.project_id:
            project = session.get(Project, payload.project_id)
            project_slug = project.slug if project is not None else ""
        config = get_or_create_trainplane_config(session)
        training_profile = {
            **json.loads(config.default_training_profile_json or "{}"),
            **payload.training_profile,
        }
        try:
            remote_payload = client.create_run(
                {
                    "project_slug": project_slug or app_settings.default_project_slug,
                    "name": payload.name,
                    "base_model_id": payload.base_model_id,
                    "dataset_bundle_id": payload.dataset_bundle_id,
                    "summary": payload.summary,
                    "training_profile": training_profile,
                }
            )
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        mirrored = mirror_remote_run(session, remote_payload, project_id=payload.project_id)
        payload_dict = {**remote_payload, "mirrored_job_id": mirrored.id}
        session.commit()
        return payload_dict

    @app.get("/api/remote/trainplane/runs/{run_id}")
    def get_remote_trainplane_run(
        run_id: str,
        project_id: str | None = None,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        try:
            payload = client.get_run(run_id)
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        mirrored = mirror_remote_run(session, payload, project_id=project_id)
        artifact = payload.get("artifact")
        if isinstance(artifact, dict) and artifact:
            mirrored_artifact = mirror_remote_artifact(session, artifact, project_id=project_id)
            payload["mirrored_artifact_id"] = mirrored_artifact.id
        payload["mirrored_job_id"] = mirrored.id
        session.commit()
        return payload

    @app.post("/api/remote/trainplane/runs/{run_id}/cancel")
    def cancel_remote_trainplane_run(
        run_id: str,
        project_id: str | None = None,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        try:
            payload = client.cancel_run(run_id)
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        mirrored = mirror_remote_run(session, payload, project_id=project_id)
        session.commit()
        return {**payload, "mirrored_job_id": mirrored.id}

    @app.get("/api/remote/trainplane/runs/{run_id}/stream")
    def stream_remote_trainplane_run(run_id: str, client=Depends(get_trainplane_client)):
        try:
            stream_url = client.stream_url(run_id)
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        def proxy_events() -> Iterator[bytes]:
            request = UrlRequest(stream_url, headers={"Accept": "text/event-stream"})
            try:
                with urlopen(request, timeout=60) as response:
                    while True:
                        chunk = response.read(2048)
                        if not chunk:
                            break
                        yield chunk
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                yield _sse("error", {"detail": detail or f"HTTP {exc.code}"}).encode("utf-8")
            except (URLError, OSError) as exc:
                yield _sse("error", {"detail": str(exc)}).encode("utf-8")

        return StreamingResponse(proxy_events(), media_type="text/event-stream")

    @app.get("/api/remote/trainplane/artifacts")
    def list_remote_trainplane_artifacts(
        project_id: str | None = None,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> list[dict[str, object]]:
        try:
            payload = client.list_artifacts()
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        results: list[dict[str, object]] = []
        for item in payload:
            mirrored = mirror_remote_artifact(session, item, project_id=project_id)
            results.append({**item, "mirrored_artifact_id": mirrored.id})
        session.commit()
        return results

    @app.post("/api/remote/trainplane/artifacts/{artifact_id}/merge")
    def merge_remote_trainplane_artifact(
        artifact_id: str,
        project_id: str | None = None,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        try:
            payload = client.merge_artifact(artifact_id)
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        mirrored = mirror_remote_artifact(session, payload, project_id=project_id)
        session.commit()
        return {**payload, "mirrored_artifact_id": mirrored.id}

    @app.post("/api/remote/trainplane/artifacts/{artifact_id}/promote")
    def promote_remote_trainplane_artifact(
        artifact_id: str,
        project_id: str | None = None,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        try:
            payload = client.promote_artifact(artifact_id)
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        mirrored = mirror_remote_artifact(session, payload, project_id=project_id)
        session.commit()
        return {**payload, "mirrored_artifact_id": mirrored.id}

    @app.get("/api/remote/trainplane/evaluations")
    def list_remote_trainplane_evaluations(client=Depends(get_trainplane_client)) -> list[dict[str, object]]:
        try:
            return client.list_evaluations()
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/remote/trainplane/evaluations")
    def create_remote_trainplane_evaluation(
        payload: RemoteTrainPlaneEvaluationRequest,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        cases = build_prompt_cases(payload.prompts, payload.cases)
        if not cases:
            raise HTTPException(status_code=400, detail="Nenhum prompt/case disponível para avaliação.")
        cases, resolved_ref = complete_local_baseline_cases(
            session=session,
            baseline_mode=payload.baseline_mode,
            baseline_provider_id=payload.baseline_provider_id,
            baseline_model_name=payload.baseline_model_name,
            cases=cases,
        )
        try:
            return client.create_evaluation(
                {
                    "candidate_artifact_id": payload.candidate_artifact_id,
                    "baseline_mode": payload.baseline_mode,
                    "baseline_ref": payload.baseline_ref or resolved_ref,
                    "suite_name": payload.suite_name,
                    "cases": cases,
                    "metadata": {
                        **payload.metadata,
                        "project_id": payload.project_id,
                        "session_id": payload.session_id,
                    },
                }
            )
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/remote/trainplane/comparisons")
    def list_remote_trainplane_comparisons(client=Depends(get_trainplane_client)) -> list[dict[str, object]]:
        try:
            return client.list_comparisons()
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/remote/trainplane/comparisons")
    def create_remote_trainplane_comparison(
        payload: RemoteTrainPlaneComparisonRequest,
        session: Session = Depends(get_session),
        client=Depends(get_trainplane_client),
    ) -> dict[str, object]:
        cases = build_prompt_cases(payload.prompts, payload.cases)
        if not cases:
            raise HTTPException(status_code=400, detail="Nenhum prompt/case disponível para comparação.")
        cases, resolved_ref = complete_local_baseline_cases(
            session=session,
            baseline_mode=payload.baseline_mode,
            baseline_provider_id=payload.baseline_provider_id,
            baseline_model_name=payload.baseline_model_name,
            cases=cases,
        )
        try:
            return client.create_comparison(
                {
                    "candidate_artifact_id": payload.candidate_artifact_id,
                    "baseline_mode": payload.baseline_mode,
                    "baseline_ref": payload.baseline_ref or resolved_ref,
                    "prompt_set_name": payload.prompt_set_name,
                    "cases": cases,
                    "metadata": {
                        **payload.metadata,
                        "project_id": payload.project_id,
                        "session_id": payload.session_id,
                    },
                }
            )
        except TrainPlaneClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

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
