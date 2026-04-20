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
    capabilities_json: str = "[]"
    config_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class RuntimeMetadata(SQLModel, table=True):
    __tablename__ = "runtime_metadata"

    key: str = Field(primary_key=True)
    value: str = ""
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


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
