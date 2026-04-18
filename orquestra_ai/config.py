from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OrquestraSettings:
    workspace_root: Path
    api_host: str
    api_port: int
    database_url: str
    artifacts_root: Path
    default_project_slug: str
    default_provider_id: str
    local_chat_model: str
    local_reasoning_model: str
    local_embedding_model: str
    remote_chat_model: str
    litellm_proxy_url: str | None
    web_enabled: bool
    redis_url: str
    qdrant_url: str | None
    qdrant_path: Path
    memory_cache_budget_mb: int
    workspace_cache_budget_mb: int
    workspace_preview_max_bytes: int

    @property
    def database_path(self) -> Path | None:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            return Path(self.database_url.removeprefix(prefix))
        return None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def load_settings(workspace_root: Path | None = None) -> OrquestraSettings:
    root = (workspace_root or Path(__file__).resolve().parents[1]).expanduser().resolve()
    artifacts_root = root / "experiments" / "orquestra"
    default_db_path = artifacts_root / "orquestra_v2.db"
    database_url = os.getenv("ORQUESTRA_DATABASE_URL") or f"sqlite:///{default_db_path}"
    qdrant_path = Path(os.getenv("ORQUESTRA_QDRANT_PATH", str(artifacts_root / "qdrant"))).expanduser()

    return OrquestraSettings(
        workspace_root=root,
        api_host=os.getenv("ORQUESTRA_API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("ORQUESTRA_API_PORT", "8808")),
        database_url=database_url,
        artifacts_root=artifacts_root,
        default_project_slug=os.getenv("ORQUESTRA_DEFAULT_PROJECT", "orquestra-lab"),
        default_provider_id=os.getenv("ORQUESTRA_DEFAULT_PROVIDER", "lmstudio"),
        local_chat_model=os.getenv("ORQUESTRA_LOCAL_CHAT_MODEL", os.getenv("DEFAULT_MODEL", "ministral")),
        local_reasoning_model=os.getenv("ORQUESTRA_LOCAL_REASONING_MODEL", os.getenv("DEFAULT_MODEL", "ministral")),
        local_embedding_model=os.getenv(
            "ORQUESTRA_LOCAL_EMBEDDING_MODEL",
            os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        ),
        remote_chat_model=os.getenv("ORQUESTRA_REMOTE_CHAT_MODEL", "deepseek-chat"),
        litellm_proxy_url=os.getenv("ORQUESTRA_LITELLM_PROXY_URL") or None,
        web_enabled=_env_bool("ORQUESTRA_ENABLE_WEB", True),
        redis_url=os.getenv("ORQUESTRA_REDIS_URL", "redis://127.0.0.1:6379/0"),
        qdrant_url=os.getenv("ORQUESTRA_QDRANT_URL") or None,
        qdrant_path=qdrant_path,
        memory_cache_budget_mb=_env_int("ORQUESTRA_MEMORY_CACHE_BUDGET_MB", 256),
        workspace_cache_budget_mb=_env_int("ORQUESTRA_WORKSPACE_CACHE_BUDGET_MB", 512),
        workspace_preview_max_bytes=_env_int("ORQUESTRA_WORKSPACE_PREVIEW_MAX_BYTES", 6000000),
    )
