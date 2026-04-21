from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    description: str = ""
    default_provider_id: str = "lmstudio"
    default_model: str = "ministral"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class ProviderProfile(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    provider_id: str = Field(index=True, unique=True)
    label: str
    transport: str = "litellm"
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    default_model: Optional[str] = None
    model_prefix: Optional[str] = None
    enabled: bool = True
    secret_ref: Optional[str] = None
    health_status: str = "unknown"
    last_checked_at: Optional[datetime] = None
    routing_tags_json: str = "[]"
    cost_profile_json: str = "{}"
    privacy_level: str = "standard"
    supports_tools: bool = False
    capabilities_json: str = "[]"
    config_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class RuntimeMetadata(SQLModel, table=True):
    __tablename__ = "runtime_metadata"

    key: str = Field(primary_key=True)
    value: str = ""
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class RuntimeSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value_json: str = "{}"
    category: str = Field(default="runtime", index=True)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class StorageLocation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    label: str
    backend: str = Field(default="local_path", index=True)
    base_uri: str
    enabled: bool = True
    priority: int = 100
    quota_bytes: Optional[int] = None
    used_bytes: int = 0
    health_status: str = "unknown"
    last_checked_at: Optional[datetime] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class StorageAssignment(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    domain: str = Field(index=True, unique=True)
    location_id: str = Field(foreign_key="storagelocation.id", index=True)
    mode: str = "hot"
    relative_path: str = ""
    quota_bytes: Optional[int] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class StorageMigrationRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    domain: str = Field(index=True)
    source_location_id: Optional[str] = Field(default=None, foreign_key="storagelocation.id")
    target_location_id: str = Field(foreign_key="storagelocation.id", index=True)
    action: str = "migrate"
    status: str = Field(default="planned", index=True)
    backup_path: str = ""
    result_json: str = "{}"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class SecretMetadata(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    provider_id: str = Field(index=True)
    label: str
    secret_ref: str = Field(index=True, unique=True)
    storage_backend: str = "keychain"
    status: str = "configured"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class ModelCatalogEntry(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    provider_id: str = Field(index=True)
    model_name: str = Field(index=True)
    display_name: str = ""
    context_window: Optional[int] = None
    supports_tools: bool = False
    routing_tags_json: str = "[]"
    metadata_json: str = "{}"
    last_seen_at: datetime = Field(default_factory=utc_now, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class ModelRoutePolicy(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    label: str
    mode: str = "single_best"
    task_type: str = Field(default="generic", index=True)
    preset: str = ""
    preferred_provider_id: str = ""
    preferred_model_name: str = ""
    fallback_chain_json: str = "[]"
    local_only: bool = False
    enabled: bool = True
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class AgentProfile(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    label: str
    description: str = ""
    task_tags_json: str = "[]"
    provider_id: str = ""
    model_name: str = ""
    privacy_level: str = "standard"
    enabled: bool = True
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class ModelRouteDecision(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: Optional[str] = Field(default=None, foreign_key="chatsession.id", index=True)
    task_type: str = "generic"
    mode: str = "single_best"
    provider_id: str
    model_name: str
    policy_id: Optional[str] = Field(default=None, foreign_key="modelroutepolicy.id")
    reason: str = ""
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class ChatSession(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    title: str = "Nova sessão"
    provider_id: str = "lmstudio"
    model_name: str = "ministral"
    status: str = "active"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
    last_message_at: datetime = Field(default_factory=utc_now, nullable=False)


class ChatMessage(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True)
    role: str = Field(index=True)
    content: str
    provider_id: Optional[str] = None
    model_name: Optional[str] = None
    usage_json: str = "{}"
    latency_seconds: Optional[float] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class SessionTranscript(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True, unique=True)
    storage_path: str
    message_count: int = 0
    transcript_bytes: int = 0
    last_message_id: Optional[str] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class SessionSummary(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True, unique=True)
    summary_path: str
    current_state: str = ""
    sections_json: str = "{}"
    last_message_id: Optional[str] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class SessionCompactionState(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True, unique=True)
    last_compacted_message_id: Optional[str] = None
    summary_version: int = 1
    next_steps_json: str = "[]"
    preserved_recent_turns: int = 6
    compacted_message_count: int = 0
    compacted_at: datetime = Field(default_factory=utc_now, nullable=False)
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class MemoryRecord(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    session_id: Optional[str] = Field(default=None, foreign_key="chatsession.id", index=True)
    topic_id: Optional[str] = Field(default=None, foreign_key="memorytopic.id", index=True)
    scope: str = Field(index=True)
    memory_kind: str = Field(default="project", index=True)
    source: str = "manual"
    content: str
    confidence: float = 0.5
    ttl_seconds: Optional[int] = None
    approved_for_training: bool = False
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class MemoryReviewCandidate(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id", index=True)
    session_id: Optional[str] = Field(default=None, foreign_key="chatsession.id", index=True)
    scope: str = Field(default="session_memory", index=True)
    memory_kind: str = Field(default="project", index=True)
    title: str
    content: str
    rationale: str = ""
    source_message_ids_json: str = "[]"
    citations_json: str = "[]"
    confidence: float = 0.5
    status: str = Field(default="pending", index=True)
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    reviewed_at: Optional[datetime] = None


class MemoryTopic(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    scope: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    title: str
    description: str = ""
    topic_path: str
    manifest_path: str
    metadata_json: str = "{}"
    last_used_at: datetime = Field(default_factory=utc_now, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class MemoryManifestEntry(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    topic_id: str = Field(foreign_key="memorytopic.id", index=True)
    entry_kind: str = Field(index=True)
    label: str
    summary: str = ""
    source_ref: str = ""
    relevance: float = 0.5
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class TrainingCandidate(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    session_id: Optional[str] = Field(default=None, foreign_key="chatsession.id", index=True)
    source: str = "manual"
    instruction: str
    context: str = ""
    response: str
    labels_json: str = "{}"
    approved: bool = False
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class PlannerSnapshot(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True, unique=True)
    objective: str = ""
    strategy: str = ""
    next_steps_json: str = "[]"
    risks_json: str = "[]"
    metadata_json: str = "{}"
    last_planned_at: datetime = Field(default_factory=utc_now, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class SessionTask(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True)
    subject: str
    description: str = ""
    active_form: str = ""
    status: str = Field(default="pending", index=True)
    owner: str = "orquestra"
    blocked_by_json: str = "[]"
    blocks_json: str = "[]"
    position: int = 0
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class WorkflowRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: Optional[str] = Field(default=None, foreign_key="chatsession.id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="sessiontask.id", index=True)
    workflow_name: str = Field(index=True)
    status: str = Field(default="pending", index=True)
    summary: str = ""
    log_path: str = ""
    output_path: str = ""
    progress: float = 0.0
    cancel_requested: bool = False
    metadata_json: str = "{}"
    started_at: datetime = Field(default_factory=utc_now, nullable=False)
    finished_at: Optional[datetime] = None


class WorkflowStepRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="workflowrun.id", index=True)
    step_index: int = Field(index=True)
    step_type: str = Field(index=True)
    label: str
    status: str = Field(default="pending", index=True)
    input_json: str = "{}"
    output_json: str = "{}"
    metadata_json: str = "{}"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class JobRecord(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    job_family: str = Field(index=True)
    connector: str = Field(index=True)
    status: str = Field(default="queued")
    spec_json: str = "{}"
    logs_path: Optional[str] = None
    outputs_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class ModelArtifact(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    name: str = Field(index=True)
    artifact_type: str = Field(index=True)
    source_pipeline: str = "manual"
    base_model: str = ""
    storage_uri: str = ""
    format: str = "adapter-only"
    benchmark_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class RemoteTrainPlaneConfig(SQLModel, table=True):
    id: str = Field(default="default", primary_key=True)
    base_url: str = ""
    region: str = ""
    instance_id: str = ""
    bucket: str = ""
    ssm_enabled: bool = True
    token_keychain_service: str = "ai.orquestra.trainplane"
    default_training_profile_json: str = "{}"
    default_serving_profile_json: str = "{}"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintConnectorConfig(SQLModel, table=True):
    connector_id: str = Field(primary_key=True)
    label: str
    category: str = Field(index=True)
    connector_kind: str = "search_provider"
    description: str = ""
    enabled_global: bool = True
    enabled_by_default: bool = True
    project_overrides_json: str = "{}"
    requires_credential: bool = False
    credential_env: Optional[str] = None
    priority: int = 100
    health_status: str = "unknown"
    allowed_modes_json: str = "[]"
    training_allowed: bool = False
    retention_policy: str = "metadata_only"
    via_tor_allowed: bool = False
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintSourceRegistryEntry(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    source_key: str = Field(index=True, unique=True)
    connector_id: Optional[str] = Field(default=None, foreign_key="osintconnectorconfig.connector_id", index=True)
    title: str
    category: str = Field(index=True)
    access_type: str = "web"
    base_url: str = ""
    description: str = ""
    retention_policy: str = "metadata_only"
    training_allowed: bool = False
    reliability: float = 0.5
    jurisdiction_tags_json: str = "[]"
    preset_tags_json: str = "[]"
    tor_supported: bool = False
    api_auth_required: bool = False
    robots_sensitive: bool = False
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintInvestigation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id", index=True)
    session_id: Optional[str] = Field(default=None, foreign_key="chatsession.id", index=True)
    title: str
    objective: str = ""
    target_entity: str = ""
    language: str = "pt-BR"
    jurisdiction: str = "global"
    mode: str = "balanced"
    status: str = Field(default="active", index=True)
    enabled_connector_ids_json: str = "[]"
    source_registry_ids_json: str = "[]"
    allowed_domains_json: str = "[]"
    blocked_domains_json: str = "[]"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    investigation_id: str = Field(foreign_key="osintinvestigation.id", index=True)
    run_kind: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    query: str = ""
    connector_ids_json: str = "[]"
    via_tor: bool = False
    log_path: str = ""
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintSource(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    investigation_id: Optional[str] = Field(default=None, foreign_key="osintinvestigation.id", index=True)
    run_id: Optional[str] = Field(default=None, foreign_key="osintrun.id", index=True)
    registry_entry_id: Optional[str] = Field(default=None, foreign_key="osintsourceregistryentry.id", index=True)
    connector_id: str = Field(index=True)
    provider: str = ""
    title: str = ""
    url: str
    canonical_url: str = ""
    snippet: str = ""
    rank: int = 0
    search_query: str = ""
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintCapture(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    investigation_id: Optional[str] = Field(default=None, foreign_key="osintinvestigation.id", index=True)
    source_id: Optional[str] = Field(default=None, foreign_key="osintsource.id", index=True)
    connector_id: str = Field(index=True)
    url: str
    canonical_url: str = ""
    title: str = ""
    content_type: str = ""
    content_hash: str = Field(index=True)
    snapshot_path: str = ""
    normalized_path: str = ""
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=utc_now, nullable=False)
    via_tor: bool = False
    license_policy: str = "metadata_only"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintEvidence(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    investigation_id: str = Field(foreign_key="osintinvestigation.id", index=True)
    source_id: Optional[str] = Field(default=None, foreign_key="osintsource.id", index=True)
    capture_id: Optional[str] = Field(default=None, foreign_key="osintcapture.id", index=True)
    title: str
    content: str
    validation_status: str = Field(default="pending", index=True)
    source_quality: float = 0.5
    entity_ids_json: str = "[]"
    claim_ids_json: str = "[]"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintClaim(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    investigation_id: str = Field(foreign_key="osintinvestigation.id", index=True)
    evidence_ids_json: str = "[]"
    title: str
    content: str
    confidence: float = 0.5
    status: str = Field(default="pending", index=True)
    memory_record_id: Optional[str] = Field(default=None, foreign_key="memoryrecord.id", index=True)
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OsintEntity(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    investigation_id: str = Field(foreign_key="osintinvestigation.id", index=True)
    name: str
    entity_type: str = Field(default="generic", index=True)
    aliases_json: str = "[]"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class ProjectDeployment(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    artifact_id: str = Field(foreign_key="modelartifact.id", index=True)
    environment: str = "local"
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class WorkspaceScan(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    root_path: str
    prompt_hint: str = ""
    status: str = "queued"
    total_assets: int = 0
    total_bytes: int = 0
    inventory_path: str = ""
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class WorkspaceAsset(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    scan_id: str = Field(foreign_key="workspacescan.id", index=True)
    absolute_path: str
    relative_path: str = Field(index=True)
    parent_relative_path: Optional[str] = None
    asset_kind: str = Field(index=True)
    mime_type: str = ""
    extension: str = ""
    size_bytes: int = 0
    sha256: str = ""
    depth: int = 0
    modified_at: datetime = Field(default_factory=utc_now, nullable=False)
    title: str = ""
    summary_excerpt: str = ""
    extraction_state: str = "inventory_only"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class WorkspaceDerivative(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    asset_id: str = Field(foreign_key="workspaceasset.id", index=True)
    derivative_kind: str = Field(index=True)
    storage_path: str
    media_type: str = ""
    expires_at: Optional[datetime] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class WorkspaceInsight(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    scan_id: str = Field(foreign_key="workspacescan.id", index=True)
    asset_id: Optional[str] = Field(default=None, foreign_key="workspaceasset.id", index=True)
    kind: str = Field(index=True)
    title: str
    content: str
    relevance: float = 0.5
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
