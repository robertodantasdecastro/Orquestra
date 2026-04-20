from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainPlaneSettings:
    workspace_root: Path
    storage_root: Path
    database_url: str
    host: str
    port: int
    public_base_url: str
    run_tick_seconds: float
    metrics_retention_limit: int
    allow_bootstrap: bool

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


def load_settings(workspace_root: Path | None = None) -> TrainPlaneSettings:
    root = (workspace_root or Path(__file__).resolve().parents[1]).expanduser().resolve()
    storage_root = Path(os.getenv("TRAINPLANE_STORAGE_ROOT", str(root / "experiments" / "trainplane"))).expanduser().resolve()
    database_url = os.getenv("TRAINPLANE_DATABASE_URL") or f"sqlite:///{storage_root / 'trainplane.db'}"
    host = os.getenv("TRAINPLANE_HOST", "127.0.0.1")
    port = int(os.getenv("TRAINPLANE_PORT", "8818"))
    public_base_url = os.getenv("TRAINPLANE_PUBLIC_BASE_URL", f"http://{host}:{port}")
    return TrainPlaneSettings(
        workspace_root=root,
        storage_root=storage_root,
        database_url=database_url,
        host=host,
        port=port,
        public_base_url=public_base_url.rstrip("/"),
        run_tick_seconds=float(os.getenv("TRAINPLANE_RUN_TICK_SECONDS", "0.12")),
        metrics_retention_limit=int(os.getenv("TRAINPLANE_METRICS_RETENTION_LIMIT", "500")),
        allow_bootstrap=_env_bool("TRAINPLANE_ALLOW_BOOTSTRAP", True),
    )
