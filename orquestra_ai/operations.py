from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlmodel import Session, select

from .config import OrquestraSettings
from .connectors import list_connector_descriptors
from .models import (
    ChatMessage,
    ChatSession,
    JobRecord,
    MemoryRecord,
    MemoryReviewCandidate,
    MemoryTopic,
    ModelArtifact,
    Project,
    ProviderProfile,
    TrainingCandidate,
    WorkflowRun,
    WorkspaceAsset,
    WorkspaceScan,
)
from .runtime_state import collect_runtime_state, resolve_dmg_bundle_path
from .services import (
    job_record_to_dict,
    memory_record_to_dict,
    memory_review_candidate_to_dict,
    memory_topic_to_dict,
    model_artifact_to_dict,
    project_to_dict,
    provider_profile_to_dict,
    workspace_scan_to_dict,
    workflow_run_to_dict,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _tcp_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ready(url: str, timeout: float = 0.8) -> bool:
    request = Request(url, headers={"User-Agent": "OrquestraOps/0.2"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except HTTPError as exc:
        return 200 <= exc.code < 500
    except (URLError, OSError, ValueError):
        return False


def _tail_text(path: Path, max_lines: int = 40, max_bytes: int = 12000) -> str:
    if not path.exists():
        return ""
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]
    text = raw.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _run_capture(*args: str) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return ""
    return (result.stdout or "").strip()


def _parse_process_rows(raw: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        try:
            pid = int(parts[0])
        except (ValueError, IndexError):
            pid = 0
        command = parts[1] if len(parts) > 1 else stripped
        rows.append(
            {
                "pid": pid,
                "command": command,
                "summary": command[:140],
            }
        )
    return rows


def _tmux_sessions() -> list[str]:
    raw = _run_capture("tmux", "ls")
    sessions: list[str] = []
    for line in raw.splitlines():
        label = line.split(":", 1)[0].strip()
        if label:
            sessions.append(label)
    return sessions


def _url_host_port(raw_url: str, default_port: int) -> tuple[str, int]:
    parsed = urlparse(raw_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or default_port
    return host, port


@dataclass
class OperationAction:
    action_id: str
    label: str
    summary: str
    command_preview: str
    kind: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class OperationRun:
    run_id: str
    action_id: str
    label: str
    status: str
    command: str
    cwd: str
    log_path: str
    started_at: str
    finished_at: str | None = None
    exit_code: int | None = None

    def to_dict(self, *, include_tail: bool = False) -> dict[str, object]:
        payload = asdict(self)
        payload["log_tail"] = _tail_text(Path(self.log_path)) if include_tail else ""
        return payload


class OrquestraOperations:
    def __init__(self, settings: OrquestraSettings) -> None:
        self.settings = settings
        self.root = settings.workspace_root
        self.runtime_dir = settings.artifacts_root / "operations"
        self.logs_dir = self.runtime_dir / "logs"
        self.manifests_dir = self.runtime_dir / "manifests"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._runs: dict[str, OperationRun] = {}
        self._actions = {
            action.action_id: action
            for action in (
                OperationAction(
                    action_id="bootstrap",
                    label="Bootstrap Local",
                    summary="Prepara Python, dependências web e ambiente local do Orquestra.",
                    command_preview="./scripts/bootstrap_orquestra.sh",
                    kind="setup",
                ),
                OperationAction(
                    action_id="validate",
                    label="Validar Stack",
                    summary="Executa py_compile, build web, cargo check e smoke local da API.",
                    command_preview="./scripts/validate_orquestra.sh",
                    kind="validation",
                ),
                OperationAction(
                    action_id="build_web",
                    label="Build Web",
                    summary="Compila o frontend React/Vite para distribuição local.",
                    command_preview="./scripts/build_orquestra_web.sh",
                    kind="build",
                ),
                OperationAction(
                    action_id="build_desktop",
                    label="Build Desktop",
                    summary="Gera o app macOS e o DMG do Orquestra.",
                    command_preview="cd orquestra_web && npm run desktop:build",
                    kind="build",
                ),
                OperationAction(
                    action_id="install_macos",
                    label="Instalar no macOS",
                    summary="Instala o app em ~/Applications e registra um LaunchAgent local da API.",
                    command_preview="./scripts/install_orquestra_macos.sh",
                    kind="install",
                ),
                OperationAction(
                    action_id="uninstall_macos",
                    label="Desinstalar no macOS",
                    summary="Remove app instalado e LaunchAgent local; preserva dados por padrão.",
                    command_preview="./scripts/uninstall_orquestra_macos.sh",
                    kind="install",
                ),
            )
        }
        self._load_runs()

    def _load_runs(self) -> None:
        for path in sorted(self.manifests_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                run = OperationRun(**payload)
            except Exception:
                continue
            self._runs[run.run_id] = run

    def _write_run(self, run: OperationRun) -> None:
        target = self.manifests_dir / f"{run.run_id}.json"
        target.write_text(json.dumps(asdict(run), ensure_ascii=False, indent=2), encoding="utf-8")

    def list_actions(self) -> list[dict[str, object]]:
        return [action.to_dict() for action in self._actions.values()]

    def get_action(self, action_id: str) -> OperationAction:
        action = self._actions.get(action_id)
        if action is None:
            raise KeyError(action_id)
        return action

    def list_runs(self, limit: int = 12) -> list[dict[str, object]]:
        with self._lock:
            runs = sorted(self._runs.values(), key=lambda item: item.started_at, reverse=True)
        return [run.to_dict(include_tail=True) for run in runs[:limit]]

    def get_run(self, run_id: str) -> dict[str, object]:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        return run.to_dict(include_tail=True)

    def start_action(self, action_id: str) -> dict[str, object]:
        action = self._actions.get(action_id)
        if action is None:
            raise KeyError(action_id)

        run_id = str(uuid.uuid4())
        log_path = self.logs_dir / f"{run_id}.log"
        run = OperationRun(
            run_id=run_id,
            action_id=action.action_id,
            label=action.label,
            status="running",
            command=action.command_preview,
            cwd=str(self.root),
            log_path=str(log_path),
            started_at=_utc_now(),
        )
        with self._lock:
            self._runs[run_id] = run
            self._write_run(run)

        thread = threading.Thread(target=self._run_action, args=(run_id, action), daemon=True)
        thread.start()
        return run.to_dict(include_tail=True)

    def _run_action(self, run_id: str, action: OperationAction) -> None:
        log_path = self.logs_dir / f"{run_id}.log"
        return_code = self.run_action_sync(action.action_id, log_path=log_path)

        with self._lock:
            run = self._runs[run_id]
            run.status = "succeeded" if return_code == 0 else "failed"
            run.exit_code = return_code
            run.finished_at = _utc_now()
            self._write_run(run)

    def run_action_sync(
        self,
        action_id: str,
        *,
        log_path: str | Path,
        cancel_event: threading.Event | None = None,
    ) -> int:
        action = self.get_action(action_id)
        return self._execute_command(action.action_id, action.command_preview, log_path=Path(log_path), cancel_event=cancel_event)

    def _execute_command(
        self,
        action_id: str,
        command: str,
        *,
        log_path: Path,
        cancel_event: threading.Event | None = None,
    ) -> int:
        env = os.environ.copy()
        env.setdefault("ORQUESTRA_ROOT", str(self.root))
        env.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

        with log_path.open("w", encoding="utf-8") as handle:
            handle.write(f"[orquestra-ops] action={action_id}\n")
            handle.write(f"[orquestra-ops] started_at={_utc_now()}\n")
            handle.write(f"[orquestra-ops] command={command}\n\n")
            handle.flush()

            process = subprocess.Popen(
                ["/bin/bash", "-lc", command],
                cwd=self.root,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    process.terminate()
                    try:
                        return_code = process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        return_code = process.wait()
                    handle.write("\n[orquestra-ops] cancelled=true\n")
                    handle.write(f"[orquestra-ops] exit_code={return_code}\n")
                    return return_code
                return_code = process.poll()
                if return_code is not None:
                    handle.write(f"\n[orquestra-ops] exit_code={return_code}\n")
                    return return_code
                time.sleep(0.2)

    def dashboard(self, session: Session) -> dict[str, object]:
        projects = session.exec(select(Project).order_by(Project.created_at.desc())).all()
        providers = session.exec(select(ProviderProfile).order_by(ProviderProfile.provider_id)).all()
        training_jobs = session.exec(select(JobRecord).where(JobRecord.job_family == "training").order_by(JobRecord.created_at.desc())).all()
        remote_jobs = session.exec(select(JobRecord).where(JobRecord.job_family == "remote").order_by(JobRecord.created_at.desc())).all()
        workflow_runs = session.exec(select(WorkflowRun).order_by(WorkflowRun.started_at.desc()).limit(10)).all()
        registry_models = session.exec(select(ModelArtifact).order_by(ModelArtifact.created_at.desc())).all()
        recent_sessions = session.exec(select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(8)).all()
        recent_scans = session.exec(select(WorkspaceScan).order_by(WorkspaceScan.updated_at.desc()).limit(8)).all()
        recent_records = session.exec(select(MemoryRecord).order_by(MemoryRecord.created_at.desc()).limit(10)).all()
        recent_topics = session.exec(select(MemoryTopic).order_by(MemoryTopic.updated_at.desc()).limit(8)).all()
        recent_review_candidates = session.exec(select(MemoryReviewCandidate).order_by(MemoryReviewCandidate.created_at.desc()).limit(10)).all()
        recent_candidates = session.exec(select(TrainingCandidate).order_by(TrainingCandidate.created_at.desc()).limit(8)).all()
        message_count = len(session.exec(select(ChatMessage)).all())
        memory_records = session.exec(select(MemoryRecord)).all()
        memory_topics = session.exec(select(MemoryTopic)).all()
        scans = session.exec(select(WorkspaceScan)).all()
        assets = session.exec(select(WorkspaceAsset)).all()

        scope_counts: dict[str, int] = {}
        for record in memory_records:
            scope_counts[record.scope] = scope_counts.get(record.scope, 0) + 1

        connectors = [item.to_dict() for item in list_connector_descriptors()]
        services = self._collect_services()
        ready_connectors = len([item for item in connectors if item["ready"]])
        ready_services = len([item for item in services if item["ready"]])
        runtime_state = collect_runtime_state(self.settings)
        runtime_manifest = runtime_state.get("manifest") or {}
        source_root_value = runtime_manifest.get("source_root")
        source_root = Path(str(source_root_value)) if source_root_value else self.root
        if not source_root.exists():
            source_root = self.root
        installed_app_value = runtime_manifest.get("install_dir")
        installed_app = Path(str(installed_app_value)) if installed_app_value else None

        source_app_bundle = source_root / "orquestra_web" / "src-tauri" / "target" / "release" / "bundle" / "macos" / "Orquestra AI.app"
        app_bundle = installed_app if installed_app and installed_app.exists() else source_app_bundle
        dmg_bundle = resolve_dmg_bundle_path(source_root)
        installer = source_root / "scripts" / "install_orquestra_macos.sh"
        uninstaller = source_root / "scripts" / "uninstall_orquestra_macos.sh"
        memory_dir = self.settings.artifacts_root / "memorygraph"
        workspace_dir = self.settings.artifacts_root / "workspace"
        db_path = self.settings.database_path

        return {
            "generated_at": _utc_now(),
            "services": services,
            "metrics": [
                {"id": "services_ready", "label": "Serviços prontos", "value": ready_services, "helper": "checklist local e integrações"},
                {"id": "sessions", "label": "Sessões", "value": len(recent_sessions), "helper": "histórico recente ativo"},
                {"id": "memories", "label": "Memórias", "value": len(memory_records), "helper": "registros duráveis e episódicos"},
                {"id": "review_pending", "label": "Inbox memória", "value": len([item for item in recent_review_candidates if item.status == "pending"]), "helper": "candidatos aguardando revisão"},
                {"id": "execution", "label": "Execuções", "value": len(training_jobs) + len(remote_jobs) + len(workflow_runs), "helper": "jobs, workflows e operações registradas"},
            ],
            "process_snapshot": {
                "background_processes": _parse_process_rows(_run_capture("pgrep", "-af", "orquestra|uvicorn|vite|tauri|orquestra-desktop")),
                "tmux_sessions": _tmux_sessions(),
                "listeners": {
                    "api": _tcp_open(self.settings.api_host, self.settings.api_port),
                    "web": _tcp_open("127.0.0.1", 4177),
                },
                "recent_sessions": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "provider_id": item.provider_id,
                        "model_name": item.model_name,
                        "status": item.status,
                        "created_at": item.created_at.isoformat(),
                        "updated_at": item.updated_at.isoformat(),
                        "last_message_at": item.last_message_at.isoformat(),
                    }
                    for item in recent_sessions
                ],
                "recent_scans": [workspace_scan_to_dict(item) for item in recent_scans],
                "recent_jobs": [job_record_to_dict(item) for item in (training_jobs[:4] + remote_jobs[:4])],
                "recent_workflows": [workflow_run_to_dict(item) for item in workflow_runs[:6]],
                "runtime_paths": {
                    "database": str(db_path) if db_path else self.settings.database_url,
                    "memorygraph": str(memory_dir),
                    "workspace": str(workspace_dir),
                    "qdrant": str(self.settings.qdrant_path),
                },
                "runtime_state": runtime_state,
            },
            "memory_snapshot": {
                "topics": len(memory_topics),
                "records": len(memory_records),
                "training_candidates": len(recent_candidates),
                "review_candidates": len(recent_review_candidates),
                "review_pending": len([item for item in recent_review_candidates if item.status == "pending"]),
                "message_count": message_count,
                "scope_breakdown": [{"scope": scope, "count": count} for scope, count in sorted(scope_counts.items())],
                "recent_records": [memory_record_to_dict(item) for item in recent_records],
                "recent_topics": [memory_topic_to_dict(item) for item in recent_topics],
                "recent_review_candidates": [memory_review_candidate_to_dict(item) for item in recent_review_candidates],
                "recent_candidates": [
                    {
                        "id": item.id,
                        "source": item.source,
                        "instruction": item.instruction,
                        "approved": item.approved,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in recent_candidates
                ],
                "storage": {
                    "database_size_bytes": _safe_size(db_path) if db_path else 0,
                    "memorygraph_dir_exists": memory_dir.exists(),
                    "workspace_dir_exists": workspace_dir.exists(),
                    "assets_indexed": len(assets),
                    "scans_total": len(scans),
                },
            },
            "execution_snapshot": {
                "providers": [provider_profile_to_dict(item) for item in providers],
                "projects": [project_to_dict(item) for item in projects],
                "connectors": connectors,
                "training_jobs": [job_record_to_dict(item) for item in training_jobs[:10]],
                "remote_jobs": [job_record_to_dict(item) for item in remote_jobs[:10]],
                "workflow_runs": [workflow_run_to_dict(item) for item in workflow_runs[:10]],
                "registry_models": [model_artifact_to_dict(item) for item in registry_models[:10]],
                "actions": self.list_actions(),
                "runs": self.list_runs(limit=10),
                "artifacts": {
                    "app_bundle_path": str(app_bundle),
                    "app_bundle_exists": app_bundle.exists(),
                    "installed_app_path": str(installed_app) if installed_app else "",
                    "installed_app_exists": bool(installed_app and installed_app.exists()),
                    "dmg_path": str(dmg_bundle),
                    "dmg_exists": dmg_bundle.exists(),
                    "installer_path": str(installer),
                    "installer_exists": installer.exists(),
                    "uninstaller_path": str(uninstaller),
                    "uninstaller_exists": uninstaller.exists(),
                    "connectors_ready": ready_connectors,
                },
            },
        }

    def _collect_services(self) -> list[dict[str, object]]:
        api_url = f"http://{self.settings.api_host}:{self.settings.api_port}/api/health"
        web_url = "http://127.0.0.1:4177"
        database_path = self.settings.database_path
        dist_index = self.root / "orquestra_web" / "dist" / "index.html"
        runtime_state = collect_runtime_state(self.settings)
        runtime_manifest = runtime_state.get("manifest") or {}
        source_root_value = runtime_manifest.get("source_root")
        source_root = Path(str(source_root_value)) if source_root_value else self.root
        if not source_root.exists():
            source_root = self.root
        installed_app_value = runtime_manifest.get("install_dir")
        installed_app = Path(str(installed_app_value)) if installed_app_value else None
        source_app_bundle = source_root / "orquestra_web" / "src-tauri" / "target" / "release" / "bundle" / "macos" / "Orquestra AI.app"
        app_bundle = installed_app if installed_app and installed_app.exists() else source_app_bundle
        dmg_bundle = resolve_dmg_bundle_path(source_root)
        installer = source_root / "scripts" / "install_orquestra_macos.sh"
        uninstaller = source_root / "scripts" / "uninstall_orquestra_macos.sh"

        redis_host, redis_port = _url_host_port(self.settings.redis_url, 6379)
        lmstudio_base = os.getenv("LMSTUDIO_API_BASE", "http://localhost:1234/v1").rstrip("/")
        ollama_base = os.getenv("ORQUESTRA_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        litellm_base = (self.settings.litellm_proxy_url or "").rstrip("/")

        return [
            self._service(
                service_id="api",
                label="Orquestra API",
                category="core",
                ready=_http_ready(api_url),
                status="online" if _http_ready(api_url) else "offline",
                summary="FastAPI control plane local-first.",
                detail=api_url,
                metadata={"pid": os.getpid(), "port": self.settings.api_port},
            ),
            self._service(
                service_id="web_dev",
                label="Web Dashboard",
                category="ui",
                ready=_tcp_open("127.0.0.1", 4177),
                status="online" if _tcp_open("127.0.0.1", 4177) else "idle",
                summary="Servidor Vite para o ambiente web.",
                detail=web_url,
                metadata={"port": 4177, "bundle_ready": dist_index.exists()},
            ),
            self._service(
                service_id="web_bundle",
                label="Web Bundle",
                category="ui",
                ready=dist_index.exists(),
                status="ready" if dist_index.exists() else "missing",
                summary="Frontend compilado para servir ou embutir no app desktop.",
                detail=str(dist_index),
                metadata={"size_bytes": _safe_size(dist_index)},
            ),
            self._service(
                service_id="desktop_app",
                label="Desktop App",
                category="ui",
                ready=app_bundle.exists(),
                status="ready" if app_bundle.exists() else "missing",
                summary="Bundle macOS do Orquestra.",
                detail=str(app_bundle),
                metadata={"size_bytes": _safe_size(app_bundle / "Contents" / "MacOS" / "orquestra-desktop")},
            ),
            self._service(
                service_id="desktop_dmg",
                label="Desktop DMG",
                category="ui",
                ready=dmg_bundle.exists(),
                status="ready" if dmg_bundle.exists() else "missing",
                summary="Imagem de distribuição do app desktop.",
                detail=str(dmg_bundle),
                metadata={"size_bytes": _safe_size(dmg_bundle)},
            ),
            self._service(
                service_id="database",
                label="SQLite Runtime",
                category="runtime",
                ready=bool(database_path and database_path.exists()),
                status="ready" if database_path and database_path.exists() else "missing",
                summary="Banco local do control plane.",
                detail=str(database_path) if database_path else self.settings.database_url,
                metadata={"size_bytes": _safe_size(database_path) if database_path else 0},
            ),
            self._service(
                service_id="memorygraph",
                label="MemoryGraph Store",
                category="runtime",
                ready=(self.settings.artifacts_root / "memorygraph").exists(),
                status="ready" if (self.settings.artifacts_root / "memorygraph").exists() else "missing",
                summary="Resumo, transcript e memória durável locais.",
                detail=str(self.settings.artifacts_root / "memorygraph"),
                metadata={},
            ),
            self._service(
                service_id="workspace",
                label="Workspace Runtime",
                category="runtime",
                ready=(self.settings.artifacts_root / "workspace").exists(),
                status="ready" if (self.settings.artifacts_root / "workspace").exists() else "missing",
                summary="Inventários, derivados e previews do workspace multimodal.",
                detail=str(self.settings.artifacts_root / "workspace"),
                metadata={},
            ),
            self._service(
                service_id="chroma_memory",
                label="Chroma Memory RAG",
                category="runtime",
                ready=(self.root / "experiments").exists() or (self.settings.artifacts_root / "memorygraph").exists(),
                status="ready" if (self.root / "experiments").exists() or (self.settings.artifacts_root / "memorygraph").exists() else "missing",
                summary="Coleção vetorial local orquestra_memory_v1 para memórias aprovadas.",
                detail=str(self.root / "experiments" / "rag"),
                metadata={"collection": "orquestra_memory_v1", "backend": "chroma"},
            ),
            self._service(
                service_id="qdrant",
                label="Qdrant Vector Store Futuro",
                category="runtime",
                ready=self.settings.qdrant_path.exists(),
                status="ready" if self.settings.qdrant_path.exists() else "missing",
                summary="Persistência vetorial local mantida como backend futuro/adaptável.",
                detail=self.settings.qdrant_url or str(self.settings.qdrant_path),
                metadata={"remote_url": self.settings.qdrant_url},
            ),
            self._service(
                service_id="redis",
                label="Redis",
                category="external",
                ready=_tcp_open(redis_host, redis_port),
                status="online" if _tcp_open(redis_host, redis_port) else "offline",
                summary="Fila/cache opcional para operações assíncronas.",
                detail=self.settings.redis_url,
                metadata={"host": redis_host, "port": redis_port},
            ),
            self._service(
                service_id="lmstudio",
                label="LM Studio",
                category="provider",
                ready=_http_ready(f"{lmstudio_base}/models"),
                status="online" if _http_ready(f"{lmstudio_base}/models") else "offline",
                summary="Provider local compatível com OpenAI.",
                detail=lmstudio_base,
                metadata={},
            ),
            self._service(
                service_id="ollama",
                label="Ollama",
                category="provider",
                ready=_http_ready(f"{ollama_base}/api/tags"),
                status="online" if _http_ready(f"{ollama_base}/api/tags") else "offline",
                summary="Provider local opcional para modelos residentes.",
                detail=ollama_base,
                metadata={},
            ),
            self._service(
                service_id="litellm_proxy",
                label="LiteLLM Proxy",
                category="provider",
                ready=bool(litellm_base and _http_ready(f"{litellm_base}/models")),
                status="online" if litellm_base and _http_ready(f"{litellm_base}/models") else "idle",
                summary="Agregador opcional para providers remotos.",
                detail=litellm_base or "não configurado",
                metadata={"configured": bool(litellm_base)},
            ),
            self._service(
                service_id="installer",
                label="Instaladores macOS",
                category="distribution",
                ready=installer.exists() and uninstaller.exists(),
                status="ready" if installer.exists() and uninstaller.exists() else "missing",
                summary="Scripts de instalação e remoção do Orquestra no macOS.",
                detail=str(installer),
                metadata={"uninstaller_path": str(uninstaller)},
            ),
        ]

    @staticmethod
    def _service(
        *,
        service_id: str,
        label: str,
        category: str,
        ready: bool,
        status: str,
        summary: str,
        detail: str,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        return {
            "service_id": service_id,
            "label": label,
            "category": category,
            "ready": ready,
            "status": status,
            "summary": summary,
            "detail": detail,
            "metadata": metadata,
        }
