from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlmodel import Session

from .models import RuntimeMetadata

ORQUESTRA_DB_SCHEMA_VERSION = 9
ORQUESTRA_DB_LEGACY_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_metadata(session: Session, key: str) -> RuntimeMetadata | None:
    return session.get(RuntimeMetadata, key)


def _set_metadata(session: Session, key: str, value: str) -> None:
    record = _get_metadata(session, key)
    if record is None:
        record = RuntimeMetadata(key=key, value=value)
    else:
        record.value = value
        record.updated_at = datetime.now(timezone.utc)
    session.add(record)


def detect_schema_version(engine: Engine, *, existing_tables: set[str] | None = None) -> int:
    tables = set(existing_tables) if existing_tables is not None else set(inspect(engine).get_table_names())
    if "runtime_metadata" in tables:
        with Session(engine) as session:
            record = _get_metadata(session, "schema_version")
            if record is not None:
                try:
                    return int(record.value)
                except ValueError:
                    return ORQUESTRA_DB_LEGACY_VERSION
    if tables - {"runtime_metadata"}:
        return ORQUESTRA_DB_LEGACY_VERSION
    return 0


def apply_schema_migrations(engine: Engine, *, existing_tables: set[str] | None = None) -> dict[str, Any]:
    current_version = detect_schema_version(engine, existing_tables=existing_tables)
    changed = current_version < ORQUESTRA_DB_SCHEMA_VERSION
    inspector = inspect(engine)
    tables = set(existing_tables) if existing_tables is not None else set(inspector.get_table_names())

    with engine.begin() as connection:
        if "memoryrecord" in tables:
            _ensure_column(connection, inspector, "memoryrecord", "memory_kind", "VARCHAR DEFAULT 'project'")
            connection.execute(
                text(
                    """
                    UPDATE memoryrecord
                    SET memory_kind = CASE scope
                        WHEN 'session_memory' THEN 'user'
                        WHEN 'workspace_memory' THEN 'reference'
                        WHEN 'source_fact' THEN 'reference'
                        WHEN 'persona_memory' THEN 'persona'
                        WHEN 'training_signal' THEN 'dataset'
                        WHEN 'project_memory' THEN 'project'
                        ELSE 'project'
                    END
                    WHERE memory_kind IS NULL OR TRIM(memory_kind) = ''
                    """
                )
            )
        if "memoryreviewcandidate" in tables:
            _ensure_column(connection, inspector, "memoryreviewcandidate", "memory_kind", "VARCHAR DEFAULT 'project'")
            connection.execute(
                text(
                    """
                    UPDATE memoryreviewcandidate
                    SET memory_kind = CASE scope
                        WHEN 'session_memory' THEN 'user'
                        WHEN 'workspace_memory' THEN 'reference'
                        WHEN 'source_fact' THEN 'reference'
                        WHEN 'persona_memory' THEN 'persona'
                        WHEN 'training_signal' THEN 'dataset'
                        WHEN 'project_memory' THEN 'project'
                        ELSE 'project'
                    END
                    WHERE memory_kind IS NULL OR TRIM(memory_kind) = ''
                    """
                )
            )
        if "providerprofile" in tables:
            _ensure_column(connection, inspector, "providerprofile", "secret_ref", "VARCHAR")
            _ensure_column(connection, inspector, "providerprofile", "health_status", "VARCHAR DEFAULT 'unknown'")
            _ensure_column(connection, inspector, "providerprofile", "last_checked_at", "DATETIME")
            _ensure_column(connection, inspector, "providerprofile", "routing_tags_json", "VARCHAR DEFAULT '[]'")
            _ensure_column(connection, inspector, "providerprofile", "cost_profile_json", "VARCHAR DEFAULT '{}'")
            _ensure_column(connection, inspector, "providerprofile", "privacy_level", "VARCHAR DEFAULT 'standard'")
            _ensure_column(connection, inspector, "providerprofile", "supports_tools", "BOOLEAN DEFAULT 0")

    with Session(engine) as session:
        history_record = _get_metadata(session, "schema_history_json")
        try:
            history = json.loads(history_record.value) if history_record is not None and history_record.value else []
        except json.JSONDecodeError:
            history = []

        if changed:
            history.append(
                {
                    "from": current_version,
                    "to": ORQUESTRA_DB_SCHEMA_VERSION,
                    "applied_at": _utc_now(),
                }
            )
            _set_metadata(session, "schema_previous_version", str(current_version))
            _set_metadata(session, "schema_updated_at", _utc_now())
            _set_metadata(session, "schema_history_json", json.dumps(history, ensure_ascii=False))

        _set_metadata(session, "schema_version", str(ORQUESTRA_DB_SCHEMA_VERSION))
        _set_metadata(session, "schema_target_version", str(ORQUESTRA_DB_SCHEMA_VERSION))
        session.commit()

    return {
        "schema_version": ORQUESTRA_DB_SCHEMA_VERSION,
        "target_schema_version": ORQUESTRA_DB_SCHEMA_VERSION,
        "changed": changed,
        "previous_version": current_version,
    }


def _ensure_column(connection, inspector, table_name: str, column_name: str, sql_type: str) -> None:
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name in columns:
        return
    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}"))
