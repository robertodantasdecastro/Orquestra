from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_project_env(workspace_root: Path) -> None:
    load_dotenv(workspace_root / ".env")
    load_dotenv(workspace_root / "dashboards" / "langfuse" / ".env")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-_")
    return cleaned or "item"


def resolve_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in records:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )


def tmux_session_active(name: str) -> bool:
    proc = run_command(["tmux", "has-session", "-t", name])
    return proc.returncode == 0


def lmstudio_running() -> bool:
    proc = run_command(["osascript", "-e", 'application "LM Studio" is running'])
    return proc.returncode == 0 and proc.stdout.strip().lower() == "true"


def disk_free_gb(path: Path) -> float:
    usage = os.statvfs(str(path))
    return (usage.f_bavail * usage.f_frsize) / 1024 / 1024 / 1024


def read_memory_pressure_free_percent() -> float | None:
    proc = run_command(["memory_pressure", "-Q"])
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if "System-wide memory free percentage" in line:
            _, raw_value = line.split(":", 1)
            cleaned = raw_value.strip().rstrip("%")
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def current_timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def render_prompt(template: str, record: dict[str, Any]) -> str:
    instruction = str(record.get("instruction", "")).strip()
    input_text = str(record.get("input", "")).strip()
    context = str(record.get("context", "")).strip()
    output = str(record.get("output", "")).strip()
    return (
        template.replace("{instruction}", instruction)
        .replace("{input}", input_text)
        .replace("{context}", context)
        .replace("{output}", output)
    )


@dataclass
class RuntimePaths:
    workspace_root: Path
    runtime_root: Path
    hf_home: Path
    checkpoints_root: Path
    adapters_root: Path
    raw_html_root: Path
    experiments_root: Path
    runs_dir: Path
    ingestion_dir: Path
    reports_dir: Path
    current_run_file: Path
    current_pid_file: Path
    datasets_web_raw_root: Path
    datasets_web_curated_root: Path
    profiles_dir: Path
    prompt_templates_dir: Path
    manifests_dir: Path
    web_sources_dir: Path
    evaluation_dir: Path
    tests_runtime_root: Path

    @classmethod
    def load(cls, workspace_root: Path) -> "RuntimePaths":
        load_project_env(workspace_root)
        runtime_root = Path(
            os.getenv("LOCAL_TRAIN_RUNTIME_ROOT", "/Volumes/SSDExterno/Orquestra_runtime")
        ).expanduser()
        return cls(
            workspace_root=workspace_root,
            runtime_root=runtime_root,
            hf_home=runtime_root / "hf_cache",
            checkpoints_root=runtime_root / "local_training" / "checkpoints",
            adapters_root=runtime_root / "local_training" / "adapters",
            raw_html_root=runtime_root / "local_training" / "web_raw_html",
            experiments_root=workspace_root / "experiments" / "local_train",
            runs_dir=workspace_root / "experiments" / "local_train" / "runs",
            ingestion_dir=workspace_root / "experiments" / "local_train" / "ingestion",
            reports_dir=workspace_root / "experiments" / "local_train" / "reports",
            current_run_file=workspace_root / "experiments" / "local_train" / "current_run.json",
            current_pid_file=workspace_root / "experiments" / "local_train" / "current_pid.json",
            datasets_web_raw_root=workspace_root / "datasets" / "web_raw",
            datasets_web_curated_root=workspace_root / "datasets" / "web_curated",
            profiles_dir=workspace_root / "training" / "local" / "profiles",
            prompt_templates_dir=workspace_root / "training" / "local" / "prompt_templates",
            manifests_dir=workspace_root / "training" / "local" / "manifests",
            web_sources_dir=workspace_root / "training" / "local" / "web_sources",
            evaluation_dir=workspace_root / "training" / "local" / "evaluation",
            tests_runtime_root=workspace_root / "experiments" / "local_train" / "selftests",
        )

    def ensure(self) -> None:
        for path in (
            self.hf_home,
            self.checkpoints_root,
            self.adapters_root,
            self.raw_html_root,
            self.runs_dir,
            self.ingestion_dir,
            self.reports_dir,
            self.datasets_web_raw_root,
            self.datasets_web_curated_root,
            self.tests_runtime_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def apply_runtime_env(self) -> None:
        self.ensure()
        os.environ.setdefault("HF_HOME", str(self.hf_home))
        os.environ.setdefault("TRANSFORMERS_CACHE", str(self.hf_home / "transformers"))
        os.environ.setdefault("HF_DATASETS_CACHE", str(self.hf_home / "datasets"))
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(self.hf_home / "hub"))
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@dataclass
class ProfileConfig:
    profile_name: str
    enabled_by_default: bool
    model_id: str
    sequence_length: int
    num_train_epochs: float
    learning_rate: float
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    gradient_accumulation_steps: int
    logging_steps: int
    save_strategy: str
    save_total_limit: int
    max_train_samples: int | None
    max_eval_samples: int | None
    max_new_tokens: int
    device_preference: str
    allow_mps: bool
    allow_stack: bool
    enabled_for_general_use: bool

    @classmethod
    def load(cls, path: Path) -> "ProfileConfig":
        payload = read_json(path)
        return cls(**payload)


@dataclass
class LocalFilesSource:
    train_file: str
    val_file: str | None = None
    test_file: str | None = None
    max_train_samples: int | None = None
    max_eval_samples: int | None = None


@dataclass
class SplitRatios:
    train: float = 0.8
    val: float = 0.1
    test: float = 0.1


@dataclass
class WebCrawlSource:
    adapter: str
    seed_urls: list[str]
    allowed_domains: list[str]
    blocked_domains: list[str] = field(default_factory=list)
    max_depth: int = 1
    max_pages: int = 10
    follow_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    respect_robots: bool = True
    user_agent: str = "Orquestra_Crawler/1.0"
    request_timeout_seconds: int = 10
    delay_between_requests_ms: int = 250
    content_selectors: list[str] = field(default_factory=lambda: ["main", "article", "body"])
    output_format: str = "jsonl"
    curation_mode: str = "extractive_summary"
    split_ratios: SplitRatios = field(default_factory=SplitRatios)
    max_chars_per_document: int = 3000

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WebCrawlSource":
        ratios = payload.get("split_ratios") or {}
        payload = dict(payload)
        payload["split_ratios"] = SplitRatios(**ratios)
        return cls(**payload)


@dataclass
class DatasetManifest:
    manifest_version: int
    name: str
    task: str
    source_type: str
    prompt_template: str
    profile: str
    base_model: str
    local_files: LocalFilesSource | None = None
    web_crawl: WebCrawlSource | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "DatasetManifest":
        payload = read_json(path)
        local_files = payload.get("local_files")
        web_crawl = payload.get("web_crawl")
        return cls(
            manifest_version=payload["manifest_version"],
            name=payload["name"],
            task=payload["task"],
            source_type=payload["source_type"],
            prompt_template=payload["prompt_template"],
            profile=payload["profile"],
            base_model=payload["base_model"],
            local_files=LocalFilesSource(**local_files) if local_files else None,
            web_crawl=WebCrawlSource.from_dict(web_crawl) if web_crawl else None,
            metadata=payload.get("metadata") or {},
        )

    def validate(self) -> None:
        if self.task != "sft_instruction":
            raise ValueError("A tarefa suportada nesta fase e apenas 'sft_instruction'.")
        if self.source_type == "local_files" and not self.local_files:
            raise ValueError("Manifesto local_files exige bloco local_files.")
        if self.source_type == "web_crawl" and not self.web_crawl:
            raise ValueError("Manifesto web_crawl exige bloco web_crawl.")
        if self.source_type not in {"local_files", "web_crawl"}:
            raise ValueError(f"source_type nao suportado: {self.source_type}")


@dataclass
class PreflightResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    snapshot: dict[str, Any]


@dataclass
class DatasetBundle:
    source_type: str
    dataset_name: str
    train_file: Path
    val_file: Path | None
    test_file: Path | None
    origin_manifest: Path
    raw_ingestion_id: str | None = None


@dataclass
class RunState:
    run_id: str
    created_at: str
    updated_at: str
    state: str
    manifest_path: str
    profile_name: str
    dataset_name: str
    source_type: str
    base_model: str
    effective_model: str
    adapter_path: str
    checkpoint_dir: str
    report_path: str
    runtime_root: str
    pid: int | None
    device: str
    resources: dict[str, Any]
    config: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    ingestion_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_template(paths: RuntimePaths, template_name: str) -> str:
    path = paths.prompt_templates_dir / f"{template_name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Template nao encontrado: {path}")
    return path.read_text(encoding="utf-8")


def detect_active_local_stack() -> dict[str, bool]:
    return {
        "lmstudio": lmstudio_running(),
        "phoenix": tmux_session_active("orquestra-phoenix"),
        "h2o": tmux_session_active("orquestra-llmstudio"),
        "orchestrator": tmux_session_active("orquestra-orchestrator"),
        "langfuse": bool(run_command(["docker", "ps", "--format", "{{.Names}}"]).stdout.strip()),
    }


def active_stack_labels(status: dict[str, bool]) -> list[str]:
    return [name for name, enabled in status.items() if enabled]


def save_current_pid(path: Path, run_id: str) -> None:
    write_json(
        path,
        {
            "run_id": run_id,
            "pid": os.getpid(),
            "updated_at": utc_now(),
            "python": sys.executable,
        },
    )


def read_current_pid(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    return payload


def cleanup_current_pid(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def sleep_ms(value: int) -> None:
    time.sleep(max(value, 0) / 1000.0)
