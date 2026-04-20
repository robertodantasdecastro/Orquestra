from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import secrets
import time
from pathlib import Path
from typing import Any

from sqlmodel import Session, SQLModel, create_engine

from .models import (
    TPAdminUser,
    TPArtifact,
    TPBaseModel,
    TPComparisonRun,
    TPDatasetBundle,
    TPEvaluationRun,
    TPPersonalAccessToken,
    TPTrainingCheckpoint,
    TPTrainingMetricPoint,
    TPTrainingRun,
)


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_database(engine) -> None:
    SQLModel.metadata.create_all(engine)


def ensure_storage_dirs(root: Path) -> dict[str, Path]:
    paths = {
        "base_models": root / "base_models",
        "datasets": root / "datasets",
        "runs": root / "runs",
        "artifacts": root / "artifacts",
        "reports": root / "reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _json(value: str, default):
    try:
        return json.loads(value) if value else default
    except json.JSONDecodeError:
        return default


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt_value}:{password}".encode("utf-8")).hexdigest()
    return f"{salt_value}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt=salt), stored_hash)


def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(10)).decode("ascii").rstrip("=")


def generate_totp_code(secret: str, *, for_time: int | None = None, digits: int = 6, step: int = 30) -> str:
    timestamp = int(for_time if for_time is not None else math.floor(time.time()))
    counter = max(int(timestamp // step), 0)
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded.encode("ascii"))
    message = counter.to_bytes(8, "big")
    digest = hmac.new(key, message, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = ((digest[offset] & 0x7F) << 24) | ((digest[offset + 1] & 0xFF) << 16) | ((digest[offset + 2] & 0xFF) << 8) | (digest[offset + 3] & 0xFF)
    return str(code % (10**digits)).zfill(digits)


def verify_totp(secret: str, code: str, *, timestamp: int | None = None, window: int = 1) -> bool:
    ts = int(timestamp if timestamp is not None else math.floor(time.time()))
    normalized = (code or "").strip()
    for delta in range(-window, window + 1):
        if hmac.compare_digest(generate_totp_code(secret, for_time=ts + (delta * 30)), normalized):
            return True
    return False


def create_pat() -> tuple[str, str, str]:
    token = f"otp_{secrets.token_urlsafe(32)}"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token, digest, token[-4:]


def dict_admin_user(item: TPAdminUser) -> dict[str, Any]:
    return {
        "id": item.id,
        "username": item.username,
        "totp_enabled": item.totp_enabled,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def dict_token(item: TPPersonalAccessToken) -> dict[str, Any]:
    return {
        "id": item.id,
        "label": item.label,
        "token_last4": item.token_last4,
        "created_at": item.created_at.isoformat(),
        "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
        "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
    }


def dict_base_model(item: TPBaseModel) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "source_kind": item.source_kind,
        "source_ref": item.source_ref,
        "storage_uri": item.storage_uri,
        "size_bytes": item.size_bytes,
        "checksum_sha256": item.checksum_sha256,
        "format": item.format,
        "status": item.status,
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def dict_dataset_bundle(item: TPDatasetBundle) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_slug": item.project_slug,
        "name": item.name,
        "source": item.source,
        "storage_uri": item.storage_uri,
        "record_count": item.record_count,
        "stats": _json(item.stats_json, {}),
        "schema_version": item.schema_version,
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def dict_metric_point(item: TPTrainingMetricPoint) -> dict[str, Any]:
    return {
        "id": item.id,
        "run_id": item.run_id,
        "step_index": item.step_index,
        "epoch": item.epoch,
        "loss": item.loss,
        "eval_loss": item.eval_loss,
        "learning_rate": item.learning_rate,
        "grad_norm": item.grad_norm,
        "gpu_util": item.gpu_util,
        "gpu_mem_gb": item.gpu_mem_gb,
        "gpu_temp_c": item.gpu_temp_c,
        "cpu_percent": item.cpu_percent,
        "ram_percent": item.ram_percent,
        "disk_percent": item.disk_percent,
        "network_mbps": item.network_mbps,
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
    }


def dict_checkpoint(item: TPTrainingCheckpoint) -> dict[str, Any]:
    return {
        "id": item.id,
        "run_id": item.run_id,
        "step_index": item.step_index,
        "label": item.label,
        "storage_uri": item.storage_uri,
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
    }


def dict_artifact(item: TPArtifact) -> dict[str, Any]:
    return {
        "id": item.id,
        "run_id": item.run_id,
        "name": item.name,
        "artifact_type": item.artifact_type,
        "base_model_name": item.base_model_name,
        "storage_uri": item.storage_uri,
        "format": item.format,
        "status": item.status,
        "benchmark": _json(item.benchmark_json, {}),
        "serving_endpoint": _json(item.serving_endpoint_json, {}),
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def dict_training_run(item: TPTrainingRun, *, metrics: list[TPTrainingMetricPoint] | None = None, checkpoints: list[TPTrainingCheckpoint] | None = None, artifact: TPArtifact | None = None) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_slug": item.project_slug,
        "name": item.name,
        "base_model_id": item.base_model_id,
        "dataset_bundle_id": item.dataset_bundle_id,
        "status": item.status,
        "summary": item.summary,
        "profile": _json(item.profile_json, {}),
        "logs_path": item.logs_path,
        "artifact_id": item.artifact_id,
        "output": _json(item.output_json, {}),
        "current_step": item.current_step,
        "total_steps": item.total_steps,
        "cancel_requested": item.cancel_requested,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "metrics": [dict_metric_point(metric) for metric in (metrics or [])],
        "checkpoints": [dict_checkpoint(checkpoint) for checkpoint in (checkpoints or [])],
        "artifact": dict_artifact(artifact) if artifact is not None else None,
    }


def dict_evaluation_run(item: TPEvaluationRun) -> dict[str, Any]:
    return {
        "id": item.id,
        "candidate_artifact_id": item.candidate_artifact_id,
        "baseline_mode": item.baseline_mode,
        "baseline_ref": item.baseline_ref,
        "suite_name": item.suite_name,
        "status": item.status,
        "summary_scores": _json(item.summary_scores_json, {}),
        "results": _json(item.results_json, []),
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def dict_comparison_run(item: TPComparisonRun) -> dict[str, Any]:
    return {
        "id": item.id,
        "candidate_artifact_id": item.candidate_artifact_id,
        "baseline_mode": item.baseline_mode,
        "baseline_ref": item.baseline_ref,
        "prompt_set_name": item.prompt_set_name,
        "status": item.status,
        "summary_scores": _json(item.summary_scores_json, {}),
        "cases": _json(item.cases_json, []),
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }

