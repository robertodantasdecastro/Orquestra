from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlmodel import Session, select

from .config import OrquestraSettings
from .models import (
    RuntimeSetting,
    StorageAssignment,
    StorageLocation,
    StorageMigrationRun,
)

HOT_BACKENDS = {"local_path", "external_drive", "cloud_mounted"}
REMOTE_COLD_BACKENDS = {"s3_compatible", "sftp", "readonly_archive"}
ACTIVE_ONLY_DOMAINS = {"sqlite_active", "rag_vector_active", "memory_hot"}

DATA_DOMAINS: dict[str, dict[str, str]] = {
    "sqlite_active": {"label": "SQLite ativo", "relative_path": "orquestra_v2.db", "mode": "hot"},
    "memory_hot": {"label": "MemoryGraph ativo", "relative_path": "memorygraph", "mode": "hot"},
    "rag_vector_active": {"label": "RAG/Chroma ativo", "relative_path": "rag_runtime", "mode": "hot"},
    "qdrant_active": {"label": "Qdrant local", "relative_path": "qdrant", "mode": "hot"},
    "osint_captures": {"label": "Evidências OSINT", "relative_path": "osint", "mode": "warm"},
    "workspace_extracts": {"label": "Workspace", "relative_path": "workspace", "mode": "warm"},
    "workflow_artifacts": {"label": "Workflows", "relative_path": "workflows", "mode": "warm"},
    "trainplane_exports": {"label": "Train Plane", "relative_path": "trainplane", "mode": "cold"},
    "dataset_exports": {"label": "Datasets", "relative_path": "exports/datasets", "mode": "cold"},
    "backups": {"label": "Backups", "relative_path": "install/backups", "mode": "cold"},
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_loads(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return fallback


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _path_from_uri(uri: str) -> Path:
    if uri.startswith("file://"):
        return Path(uri.removeprefix("file://")).expanduser()
    return Path(uri).expanduser()


def storage_location_to_dict(item: StorageLocation) -> dict[str, Any]:
    return {
        "id": item.id,
        "label": item.label,
        "backend": item.backend,
        "base_uri": item.base_uri,
        "enabled": item.enabled,
        "priority": item.priority,
        "quota_bytes": item.quota_bytes,
        "used_bytes": item.used_bytes,
        "health_status": item.health_status,
        "last_checked_at": item.last_checked_at.isoformat() if item.last_checked_at else None,
        "metadata": _json_loads(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def storage_assignment_to_dict(item: StorageAssignment) -> dict[str, Any]:
    return {
        "id": item.id,
        "domain": item.domain,
        "location_id": item.location_id,
        "mode": item.mode,
        "relative_path": item.relative_path,
        "quota_bytes": item.quota_bytes,
        "metadata": _json_loads(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def storage_migration_to_dict(item: StorageMigrationRun) -> dict[str, Any]:
    return {
        "id": item.id,
        "domain": item.domain,
        "source_location_id": item.source_location_id,
        "target_location_id": item.target_location_id,
        "action": item.action,
        "status": item.status,
        "backup_path": item.backup_path,
        "result": _json_loads(item.result_json, {}),
        "metadata": _json_loads(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


class StorageResolver:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings

    def seed_defaults(self, session: Session) -> None:
        existing = session.exec(select(StorageLocation).order_by(StorageLocation.priority)).first()
        if existing is None:
            existing = StorageLocation(
                id="local-processing-hub",
                label="Processing Hub Local",
                backend="local_path",
                base_uri=str(self.settings.artifacts_root),
                priority=1,
                health_status="ok",
                metadata_json=_json_dumps({"created_by": "bootstrap", "runtime_dir": str(self.settings.runtime_dir)}),
            )
            session.add(existing)
            session.flush()

        for domain, spec in DATA_DOMAINS.items():
            assignment = session.exec(select(StorageAssignment).where(StorageAssignment.domain == domain)).first()
            if assignment is None:
                session.add(
                    StorageAssignment(
                        domain=domain,
                        location_id=existing.id,
                        mode=spec["mode"],
                        relative_path=spec["relative_path"],
                    )
                )
        self._seed_runtime_settings(session)
        session.commit()

    def _seed_runtime_settings(self, session: Session) -> None:
        payload = {
            "runtime_dir": str(self.settings.runtime_dir),
            "runtime_config_path": str(self.settings.runtime_config_path),
            "data_root": str(self.settings.artifacts_root),
            "database_url": self.settings.database_url,
            "qdrant_path": str(self.settings.qdrant_path),
            "mode": "installed" if self.settings.runtime_config else "workspace",
        }
        record = session.get(RuntimeSetting, "runtime")
        if record is None:
            record = RuntimeSetting(key="runtime", category="runtime")
        record.value_json = _json_dumps(payload)
        record.updated_at = utc_now()
        session.add(record)

    def runtime_payload(self, session: Session) -> dict[str, Any]:
        self._seed_runtime_settings(session)
        record = session.get(RuntimeSetting, "runtime")
        return _json_loads(record.value_json if record else "{}", {})

    def write_runtime_config(self, payload: dict[str, Any]) -> Path:
        path = self.settings.runtime_config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        safe_payload = {
            "version": 1,
            "runtime_dir": str(self.settings.runtime_dir),
            "data_root": payload.get("data_root") or str(self.settings.artifacts_root),
            "database_url": payload.get("database_url") or self.settings.database_url,
            "qdrant_path": payload.get("qdrant_path") or str(self.settings.qdrant_path),
            "storage_policy": payload.get("storage_policy") or "local_processing_hub",
            "updated_at": utc_now().isoformat(),
        }
        path.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return path

    def list_locations(self, session: Session) -> list[dict[str, Any]]:
        rows = session.exec(select(StorageLocation).order_by(StorageLocation.priority, StorageLocation.label)).all()
        return [storage_location_to_dict(item) for item in rows]

    def upsert_location(self, session: Session, payload: dict[str, Any], *, location_id: str | None = None) -> StorageLocation:
        backend = str(payload.get("backend") or "local_path")
        base_uri = str(payload.get("base_uri") or "").strip()
        if not base_uri:
            raise ValueError("base_uri é obrigatório.")
        record = session.get(StorageLocation, location_id) if location_id else None
        if record is None:
            record = StorageLocation(label=str(payload.get("label") or base_uri), base_uri=base_uri, backend=backend)
        record.label = str(payload.get("label") or record.label)
        record.backend = backend
        record.base_uri = base_uri
        record.enabled = bool(payload.get("enabled", record.enabled))
        record.priority = int(payload.get("priority", record.priority))
        quota = payload.get("quota_bytes", record.quota_bytes)
        record.quota_bytes = int(quota) if quota not in (None, "") else None
        record.metadata_json = _json_dumps(payload.get("metadata") or _json_loads(record.metadata_json, {}))
        record.updated_at = utc_now()
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    def test_location(self, session: Session, location_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if location_id:
            record = session.get(StorageLocation, location_id)
            if record is None:
                raise KeyError(location_id)
            backend = record.backend
            base_uri = record.base_uri
        else:
            payload = payload or {}
            backend = str(payload.get("backend") or "local_path")
            base_uri = str(payload.get("base_uri") or "")

        result = {"ok": False, "backend": backend, "base_uri": base_uri, "status": "unknown", "detail": ""}
        if backend in HOT_BACKENDS:
            path = _path_from_uri(base_uri)
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / f".orquestra-probe-{uuid4().hex}"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                stat = shutil.disk_usage(path)
                result.update({"ok": True, "status": "ok", "free_bytes": stat.free, "total_bytes": stat.total})
            except Exception as exc:
                result.update({"status": "unavailable", "detail": str(exc)})
        elif backend in REMOTE_COLD_BACKENDS:
            result.update({"ok": True, "status": "cold_configured", "detail": "Validacao remota real fica para sync/hidratacao."})
        else:
            result.update({"status": "unsupported", "detail": f"Backend não suportado: {backend}"})

        if location_id:
            record = session.get(StorageLocation, location_id)
            if record:
                record.health_status = str(result["status"])
                record.last_checked_at = utc_now()
                session.add(record)
                session.commit()
        return result

    def list_assignments(self, session: Session) -> list[dict[str, Any]]:
        rows = session.exec(select(StorageAssignment).order_by(StorageAssignment.domain)).all()
        return [storage_assignment_to_dict(item) for item in rows]

    def update_assignment(self, session: Session, domain: str, payload: dict[str, Any]) -> StorageAssignment:
        if domain not in DATA_DOMAINS:
            raise ValueError(f"Domínio desconhecido: {domain}")
        location = session.get(StorageLocation, str(payload.get("location_id") or ""))
        if location is None:
            raise KeyError("location_id")
        if domain in ACTIVE_ONLY_DOMAINS and location.backend in REMOTE_COLD_BACKENDS:
            raise ValueError("SQLite, memória quente e RAG ativo não podem usar S3/SFTP/archive diretamente.")
        record = session.exec(select(StorageAssignment).where(StorageAssignment.domain == domain)).first()
        if record is None:
            record = StorageAssignment(domain=domain, location_id=location.id)
        record.location_id = location.id
        record.mode = str(payload.get("mode") or DATA_DOMAINS[domain]["mode"])
        record.relative_path = str(payload.get("relative_path") or DATA_DOMAINS[domain]["relative_path"])
        quota = payload.get("quota_bytes", record.quota_bytes)
        record.quota_bytes = int(quota) if quota not in (None, "") else None
        record.metadata_json = _json_dumps(payload.get("metadata") or _json_loads(record.metadata_json, {}))
        record.updated_at = utc_now()
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    def resolve_assignment_path(self, session: Session, domain: str) -> str:
        assignment = session.exec(select(StorageAssignment).where(StorageAssignment.domain == domain)).first()
        if assignment is None:
            return str(self.settings.artifacts_root / DATA_DOMAINS.get(domain, {}).get("relative_path", domain))
        location = session.get(StorageLocation, assignment.location_id)
        if location is None:
            return str(self.settings.artifacts_root / assignment.relative_path)
        if location.backend in REMOTE_COLD_BACKENDS:
            return f"{location.base_uri.rstrip('/')}/{assignment.relative_path.strip('/')}"
        return str(_path_from_uri(location.base_uri) / assignment.relative_path)

    def health_report(self, session: Session) -> dict[str, Any]:
        locations = self.list_locations(session)
        assignments = self.list_assignments(session)
        domains = [
            {
                **spec,
                "domain": domain,
                "resolved_path": self.resolve_assignment_path(session, domain),
            }
            for domain, spec in DATA_DOMAINS.items()
        ]
        return {
            "runtime": self.runtime_payload(session),
            "locations": locations,
            "assignments": assignments,
            "domains": domains,
            "policy": {
                "processing_hub_required": True,
                "remote_cold_only": sorted(REMOTE_COLD_BACKENDS),
                "active_only_domains": sorted(ACTIVE_ONLY_DOMAINS),
            },
        }

    def create_migration_plan(self, session: Session, domain: str, target_location_id: str, action: str = "migrate") -> dict[str, Any]:
        if domain not in DATA_DOMAINS:
            raise ValueError(f"Domínio desconhecido: {domain}")
        target = session.get(StorageLocation, target_location_id)
        if target is None:
            raise KeyError(target_location_id)
        if domain in ACTIVE_ONLY_DOMAINS and target.backend in REMOTE_COLD_BACKENDS:
            raise ValueError("Destino remoto frio não pode receber domínio ativo.")
        source_assignment = session.exec(select(StorageAssignment).where(StorageAssignment.domain == domain)).first()
        source_location_id = source_assignment.location_id if source_assignment else None
        run = StorageMigrationRun(
            domain=domain,
            source_location_id=source_location_id,
            target_location_id=target_location_id,
            action=action,
            status="planned",
            result_json=_json_dumps({"requires_restart": domain == "sqlite_active", "backup_recommended": True}),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return storage_migration_to_dict(run)

