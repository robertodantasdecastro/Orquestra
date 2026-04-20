from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import OrquestraSettings
from .schema_state import ORQUESTRA_DB_LEGACY_VERSION, ORQUESTRA_DB_SCHEMA_VERSION
ORQUESTRA_APP_VERSION_FALLBACK = "0.2.0"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def resolve_app_version(workspace_root: Path) -> str:
    override = os.getenv("ORQUESTRA_APP_VERSION", "").strip()
    if override:
        return override
    package_json = workspace_root / "orquestra_web" / "package.json"
    payload = _read_json(package_json)
    if payload:
        version = str(payload.get("version", "")).strip()
        if version:
            return version
    return ORQUESTRA_APP_VERSION_FALLBACK


def runtime_install_dir(settings: OrquestraSettings) -> Path:
    return settings.artifacts_root / "install"


def runtime_manifest_path(settings: OrquestraSettings) -> Path:
    return runtime_install_dir(settings) / "install_manifest.json"


def runtime_backup_dir(settings: OrquestraSettings) -> Path:
    return runtime_install_dir(settings) / "backups"


def resolve_dmg_bundle_path(workspace_root: Path) -> Path:
    dmg_dir = workspace_root / "orquestra_web" / "src-tauri" / "target" / "release" / "bundle" / "dmg"
    preferred = dmg_dir / f"Orquestra AI_{resolve_app_version(workspace_root)}_aarch64.dmg"
    if preferred.exists():
        return preferred
    candidates = sorted(
        dmg_dir.glob("Orquestra AI_*.dmg"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    return preferred


def load_runtime_manifest(settings: OrquestraSettings) -> dict[str, Any] | None:
    return _read_json(runtime_manifest_path(settings))


def list_runtime_backups(settings: OrquestraSettings) -> list[dict[str, Any]]:
    backup_dir = runtime_backup_dir(settings)
    if not backup_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(backup_dir.glob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": _iso_from_timestamp(stat.st_mtime),
            }
        )
    return rows


def detect_runtime_mode(settings: OrquestraSettings, manifest: dict[str, Any] | None = None) -> str:
    path_text = str(settings.workspace_root)
    if manifest:
        return "installed-runtime"
    if "/Library/Application Support/Orquestra/runtime" in path_text:
        return "runtime-directory"
    return "workspace"


def _read_sqlite_schema_state(database_path: Path | None) -> dict[str, Any]:
    fallback = {
        "schema_version": 0,
        "target_schema_version": ORQUESTRA_DB_SCHEMA_VERSION,
        "migration_required": True,
        "schema_updated_at": None,
    }
    if database_path is None or not database_path.exists():
        return fallback

    try:
        with sqlite3.connect(database_path) as connection:
            table_rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            tables = {str(row[0]) for row in table_rows}
            if "runtime_metadata" not in tables:
                schema_version = ORQUESTRA_DB_LEGACY_VERSION if tables else 0
                return {
                    "schema_version": schema_version,
                    "target_schema_version": ORQUESTRA_DB_SCHEMA_VERSION,
                    "migration_required": schema_version < ORQUESTRA_DB_SCHEMA_VERSION,
                    "schema_updated_at": None,
                }

            rows = connection.execute(
                "SELECT key, value, updated_at FROM runtime_metadata WHERE key IN (?, ?, ?)",
                ("schema_version", "schema_target_version", "schema_updated_at"),
            ).fetchall()
    except sqlite3.Error:
        return fallback

    metadata = {str(key): value for key, value, _updated_at in rows}
    updated_at_row = next((updated_at for key, _value, updated_at in rows if key == "schema_updated_at"), None)
    try:
        schema_version = int(str(metadata.get("schema_version", "0")))
    except ValueError:
        schema_version = 0
    try:
        target_schema_version = int(str(metadata.get("schema_target_version", ORQUESTRA_DB_SCHEMA_VERSION)))
    except ValueError:
        target_schema_version = ORQUESTRA_DB_SCHEMA_VERSION

    return {
        "schema_version": schema_version,
        "target_schema_version": target_schema_version,
        "migration_required": schema_version < target_schema_version,
        "schema_updated_at": updated_at_row,
    }


def collect_runtime_state(settings: OrquestraSettings) -> dict[str, Any]:
    manifest = load_runtime_manifest(settings)
    backups = list_runtime_backups(settings)
    schema_state = _read_sqlite_schema_state(settings.database_path)
    return {
        "app_version": resolve_app_version(settings.workspace_root),
        "schema_version": schema_state["schema_version"],
        "target_schema_version": schema_state["target_schema_version"],
        "migration_required": schema_state["migration_required"],
        "schema_updated_at": schema_state["schema_updated_at"],
        "mode": detect_runtime_mode(settings, manifest),
        "managed": manifest is not None,
        "manifest_path": str(runtime_manifest_path(settings)),
        "backup_dir": str(runtime_backup_dir(settings)),
        "backup_count": len(backups),
        "last_backup": backups[0] if backups else None,
        "backups": backups[:5],
        "manifest": manifest,
    }
