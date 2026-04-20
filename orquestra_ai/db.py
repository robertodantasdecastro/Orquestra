from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

from .schema_state import apply_schema_migrations


def build_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_database(engine: Engine) -> None:
    existing_tables = set(inspect(engine).get_table_names())
    SQLModel.metadata.create_all(engine)
    apply_schema_migrations(engine, existing_tables=existing_tables)
