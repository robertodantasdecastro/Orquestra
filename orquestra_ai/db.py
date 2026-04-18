from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine


def build_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_database(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
