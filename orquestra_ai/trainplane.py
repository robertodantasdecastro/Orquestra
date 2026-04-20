from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlmodel import Session, select

from .models import JobRecord, ModelArtifact, RemoteTrainPlaneConfig, TrainingCandidate, utc_now

TRAINPLANE_KEYCHAIN_SERVICE = "ai.orquestra.trainplane"
TRAINPLANE_KEYCHAIN_ACCOUNT = "default"


class TrainPlaneClientError(RuntimeError):
    pass


def _json(value: str, default):
    try:
        return json.loads(value) if value else default
    except json.JSONDecodeError:
        return default


def trainplane_config_to_dict(item: RemoteTrainPlaneConfig, *, token_configured: bool = False) -> dict[str, Any]:
    return {
        "id": item.id,
        "base_url": item.base_url,
        "region": item.region,
        "instance_id": item.instance_id,
        "bucket": item.bucket,
        "ssm_enabled": item.ssm_enabled,
        "token_configured": token_configured,
        "token_keychain_service": item.token_keychain_service,
        "default_training_profile": _json(item.default_training_profile_json, {}),
        "default_serving_profile": _json(item.default_serving_profile_json, {}),
        "metadata": _json(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def get_or_create_trainplane_config(session: Session) -> RemoteTrainPlaneConfig:
    item = session.get(RemoteTrainPlaneConfig, "default")
    if item is None:
        item = RemoteTrainPlaneConfig()
        session.add(item)
        session.commit()
        session.refresh(item)
    return item


def _token_file_path() -> Path | None:
    raw = Path(Path.cwd(), ".trainplane-token").expanduser()
    from os import getenv

    override = getenv("ORQUESTRA_TRAINPLANE_TOKEN_FILE")
    if override:
        return Path(override).expanduser()
    if getenv("ORQUESTRA_DISABLE_KEYCHAIN", "").lower() in {"1", "true", "yes", "on"}:
        return raw
    return None


def set_trainplane_token(token: str) -> None:
    fallback_file = _token_file_path()
    if fallback_file is not None:
        fallback_file.parent.mkdir(parents=True, exist_ok=True)
        fallback_file.write_text(token.strip(), encoding="utf-8")
        return
    subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-s",
            TRAINPLANE_KEYCHAIN_SERVICE,
            "-a",
            TRAINPLANE_KEYCHAIN_ACCOUNT,
            "-w",
            token.strip(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def get_trainplane_token() -> str:
    fallback_file = _token_file_path()
    if fallback_file is not None:
        if fallback_file.exists():
            return fallback_file.read_text(encoding="utf-8").strip()
        return ""
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            TRAINPLANE_KEYCHAIN_SERVICE,
            "-a",
            TRAINPLANE_KEYCHAIN_ACCOUNT,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


class RemoteTrainPlaneHttpClient:
    def __init__(self, config: RemoteTrainPlaneConfig, token: str) -> None:
        self.config = config
        self.token = token.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.config.base_url.strip() and self.token)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        if not self.enabled:
            raise TrainPlaneClientError("Train Plane remoto não configurado.")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.config.base_url.rstrip('/')}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                **({"Content-Type": "application/json"} if payload is not None else {}),
            },
        )
        try:
            with urlopen(request, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise TrainPlaneClientError(detail or f"HTTP {exc.code}") from exc
        except (URLError, OSError, json.JSONDecodeError) as exc:
            raise TrainPlaneClientError(str(exc)) from exc

    def health(self) -> dict[str, Any]:
        if not self.config.base_url.strip():
            raise TrainPlaneClientError("Train Plane remoto sem base_url.")
        request = Request(f"{self.config.base_url.rstrip('/')}/api/health", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise TrainPlaneClientError(detail or f"HTTP {exc.code}") from exc
        except (URLError, OSError, json.JSONDecodeError) as exc:
            raise TrainPlaneClientError(str(exc)) from exc

    def list_base_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/base-models"))  # type: ignore[arg-type]

    def init_base_model_upload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/api/base-models/upload/init", payload))  # type: ignore[arg-type]

    def complete_base_model_upload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/api/base-models/upload/complete", payload))  # type: ignore[arg-type]

    def list_dataset_bundles(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/dataset-bundles"))  # type: ignore[arg-type]

    def create_dataset_bundle(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/api/dataset-bundles", payload))  # type: ignore[arg-type]

    def list_runs(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/training-runs"))  # type: ignore[arg-type]

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/api/training-runs", payload))  # type: ignore[arg-type]

    def get_run(self, run_id: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/api/training-runs/{run_id}"))  # type: ignore[arg-type]

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return dict(self._request("POST", f"/api/training-runs/{run_id}/cancel"))  # type: ignore[arg-type]

    def list_evaluations(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/evaluation-runs"))  # type: ignore[arg-type]

    def create_evaluation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/api/evaluation-runs", payload))  # type: ignore[arg-type]

    def list_comparisons(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/comparison-runs"))  # type: ignore[arg-type]

    def create_comparison(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/api/comparison-runs", payload))  # type: ignore[arg-type]

    def list_artifacts(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/artifacts"))  # type: ignore[arg-type]

    def merge_artifact(self, artifact_id: str) -> dict[str, Any]:
        return dict(self._request("POST", f"/api/artifacts/{artifact_id}/merge"))  # type: ignore[arg-type]

    def promote_artifact(self, artifact_id: str) -> dict[str, Any]:
        return dict(self._request("POST", f"/api/artifacts/{artifact_id}/promote"))  # type: ignore[arg-type]

    def stream_url(self, run_id: str) -> str:
        if not self.enabled:
            raise TrainPlaneClientError("Train Plane remoto não configurado.")
        return f"{self.config.base_url.rstrip('/')}/api/training-runs/{run_id}/events?{urlencode({'token': self.token})}"


def build_trainplane_client(session: Session) -> RemoteTrainPlaneHttpClient:
    config = get_or_create_trainplane_config(session)
    token = get_trainplane_token()
    return RemoteTrainPlaneHttpClient(config, token)


def mirror_remote_run(session: Session, payload: dict[str, Any], *, project_id: str | None = None) -> JobRecord:
    remote_run_id = str(payload.get("id", ""))
    rows = session.exec(select(JobRecord).where(JobRecord.connector == "trainplane")).all()
    record = next((item for item in rows if str(json.loads(item.outputs_json or "{}").get("remote_run_id")) == remote_run_id), None)
    if record is None:
        record = JobRecord(project_id=project_id, job_family="remote", connector="trainplane")
    record.project_id = project_id or record.project_id
    record.status = str(payload.get("status", "queued"))
    record.spec_json = json.dumps(
        {
            "project_slug": payload.get("project_slug"),
            "name": payload.get("name"),
            "base_model_id": payload.get("base_model_id"),
            "dataset_bundle_id": payload.get("dataset_bundle_id"),
            "summary": payload.get("summary"),
        },
        ensure_ascii=False,
    )
    record.logs_path = str(payload.get("logs_path") or "")
    record.outputs_json = json.dumps(
        {
            "remote_run_id": remote_run_id,
            "artifact_id": payload.get("artifact_id"),
            "current_step": payload.get("current_step"),
            "total_steps": payload.get("total_steps"),
            "output": payload.get("output", {}),
        },
        ensure_ascii=False,
    )
    record.updated_at = utc_now()
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def mirror_remote_artifact(session: Session, payload: dict[str, Any], *, project_id: str | None = None) -> ModelArtifact:
    storage_uri = str(payload.get("storage_uri", ""))
    rows = session.exec(select(ModelArtifact).where(ModelArtifact.storage_uri == storage_uri)).all()
    record = rows[0] if rows else ModelArtifact(project_id=project_id, name=str(payload.get("name", "remote-artifact")), artifact_type=str(payload.get("artifact_type", "adapter")))
    record.project_id = project_id or record.project_id
    record.name = str(payload.get("name", record.name))
    record.artifact_type = str(payload.get("artifact_type", record.artifact_type))
    record.source_pipeline = "trainplane"
    record.base_model = str(payload.get("base_model_name", ""))
    record.storage_uri = storage_uri
    record.format = str(payload.get("format", "adapter-only"))
    record.benchmark_json = json.dumps(payload.get("benchmark", {}), ensure_ascii=False)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def build_dataset_bundle_records(session: Session, *, project_id: str | None = None, session_id: str | None = None, approved_only: bool = True, max_records: int = 200) -> list[dict[str, Any]]:
    statement = select(TrainingCandidate).order_by(TrainingCandidate.created_at.desc())
    if project_id:
        statement = statement.where(TrainingCandidate.project_id == project_id)
    if session_id:
        statement = statement.where(TrainingCandidate.session_id == session_id)
    if approved_only:
        statement = statement.where(TrainingCandidate.approved == True)  # noqa: E712
    rows = session.exec(statement.limit(max_records)).all()
    return [
        {
            "instruction": item.instruction,
            "context": item.context,
            "response": item.response,
            "labels": _json(item.labels_json, {}),
            "metadata": _json(item.metadata_json, {}),
        }
        for item in rows
    ]
