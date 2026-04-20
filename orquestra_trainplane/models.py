from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TPAdminUser(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(default="admin", index=True, unique=True)
    password_hash: str = ""
    totp_secret: str = ""
    totp_enabled: bool = False
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class TPPersonalAccessToken(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    label: str = "orquestra-local"
    token_hash: str = Field(index=True, unique=True)
    token_last4: str = ""
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class TPBaseModel(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    source_kind: str = Field(index=True)
    source_ref: str = ""
    storage_uri: str = ""
    size_bytes: int = 0
    checksum_sha256: str = ""
    format: str = "huggingface"
    status: str = Field(default="available", index=True)
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class TPDatasetBundle(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_slug: str = Field(index=True)
    name: str = Field(index=True)
    source: str = "orquestra"
    storage_uri: str = ""
    record_count: int = 0
    stats_json: str = "{}"
    schema_version: str = "orquestra-trainplane-v1"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class TPTrainingRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_slug: str = Field(index=True)
    name: str = Field(index=True)
    base_model_id: str = Field(foreign_key="tpbasemodel.id", index=True)
    dataset_bundle_id: str = Field(foreign_key="tpdatasetbundle.id", index=True)
    status: str = Field(default="queued", index=True)
    summary: str = ""
    profile_json: str = "{}"
    logs_path: str = ""
    artifact_id: Optional[str] = Field(default=None, foreign_key="tpartifact.id", index=True)
    output_json: str = "{}"
    current_step: int = 0
    total_steps: int = 0
    cancel_requested: bool = False
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TPTrainingMetricPoint(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="tptrainingrun.id", index=True)
    step_index: int = Field(index=True)
    epoch: float = 0.0
    loss: float = 0.0
    eval_loss: float = 0.0
    learning_rate: float = 0.0
    grad_norm: float = 0.0
    gpu_util: float = 0.0
    gpu_mem_gb: float = 0.0
    gpu_temp_c: float = 0.0
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    network_mbps: float = 0.0
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class TPTrainingCheckpoint(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="tptrainingrun.id", index=True)
    step_index: int = Field(index=True)
    label: str
    storage_uri: str = ""
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class TPArtifact(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    run_id: Optional[str] = Field(default=None, foreign_key="tptrainingrun.id", index=True)
    name: str = Field(index=True)
    artifact_type: str = Field(index=True)
    base_model_name: str = ""
    storage_uri: str = ""
    format: str = "adapter-only"
    status: str = Field(default="ready", index=True)
    benchmark_json: str = "{}"
    serving_endpoint_json: str = "{}"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class TPEvaluationRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    candidate_artifact_id: str = Field(foreign_key="tpartifact.id", index=True)
    baseline_mode: str = Field(index=True)
    baseline_ref: str = ""
    suite_name: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    summary_scores_json: str = "{}"
    results_json: str = "[]"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class TPComparisonRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    candidate_artifact_id: str = Field(foreign_key="tpartifact.id", index=True)
    baseline_mode: str = Field(index=True)
    baseline_ref: str = ""
    prompt_set_name: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    summary_scores_json: str = "{}"
    cases_json: str = "[]"
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
