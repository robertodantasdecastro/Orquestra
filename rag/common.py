from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from training.local.common import load_project_env, resolve_path, slugify, utc_now


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
            records.append(json.loads(line))
    return records


def _runtime_root_available(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".orquestra_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def sanitize_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    safe_payload: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe_payload[key] = value
        else:
            safe_payload[key] = json.dumps(value, ensure_ascii=False)
    return safe_payload


@dataclass
class RagPaths:
    workspace_root: Path
    runtime_root: Path
    rag_runtime_root: Path
    chroma_dir: Path
    experiments_root: Path
    ingestions_dir: Path
    interactions_dir: Path
    evaluations_dir: Path
    exports_dir: Path
    benchmarks_dir: Path
    crawl_artifacts_dir: Path
    memory_root: Path
    session_memory_dir: Path
    episodic_memory_dir: Path
    datasets_export_dir: Path
    samples_dir: Path
    benchmark_dataset: Path
    web_config_dir: Path

    @classmethod
    def load(cls, workspace_root: Path) -> "RagPaths":
        load_project_env(workspace_root)
        configured_runtime = os.getenv("RAG_RUNTIME_ROOT") or os.getenv("LOCAL_TRAIN_RUNTIME_ROOT")
        local_runtime = workspace_root / "experiments" / "orquestra" / "rag_runtime"
        runtime_root = Path(configured_runtime).expanduser() if configured_runtime else local_runtime
        if not _runtime_root_available(runtime_root):
            runtime_root = local_runtime
            runtime_root.mkdir(parents=True, exist_ok=True)
        os.environ["RAG_RUNTIME_ROOT"] = str(runtime_root)
        rag_runtime_root = runtime_root / "rag"
        return cls(
            workspace_root=workspace_root,
            runtime_root=runtime_root,
            rag_runtime_root=rag_runtime_root,
            chroma_dir=rag_runtime_root / "chroma",
            experiments_root=workspace_root / "experiments" / "rag",
            ingestions_dir=workspace_root / "experiments" / "rag" / "ingestions",
            interactions_dir=workspace_root / "experiments" / "rag" / "interactions",
            evaluations_dir=workspace_root / "experiments" / "rag" / "evaluations",
            exports_dir=workspace_root / "experiments" / "rag" / "exports",
            benchmarks_dir=workspace_root / "experiments" / "rag" / "benchmarks",
            crawl_artifacts_dir=workspace_root / "experiments" / "rag" / "crawl_artifacts",
            memory_root=workspace_root / "experiments" / "rag" / "memory",
            session_memory_dir=workspace_root / "experiments" / "rag" / "memory" / "sessions",
            episodic_memory_dir=workspace_root / "experiments" / "rag" / "memory" / "episodic",
            datasets_export_dir=workspace_root / "datasets" / "rag_exports",
            samples_dir=workspace_root / "rag" / "samples",
            benchmark_dataset=workspace_root / "rag" / "benchmarks" / "shell_programming_reference.jsonl",
            web_config_dir=workspace_root / "rag" / "configs",
        )

    def ensure(self) -> None:
        for path in (
            self.rag_runtime_root,
            self.chroma_dir,
            self.experiments_root,
            self.ingestions_dir,
            self.interactions_dir,
            self.evaluations_dir,
            self.exports_dir,
            self.benchmarks_dir,
            self.crawl_artifacts_dir,
            self.memory_root,
            self.session_memory_dir,
            self.episodic_memory_dir,
            self.datasets_export_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def apply_runtime_env(self) -> None:
        self.ensure()
        hf_home = self.runtime_root / "hf_cache"
        os.environ.setdefault("HF_HOME", str(hf_home))
        os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_home / "transformers"))
        os.environ.setdefault("HF_DATASETS_CACHE", str(hf_home / "datasets"))
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(self.rag_runtime_root / "sentence_transformers"))
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@dataclass
class RagChunk:
    chunk_id: str
    document_id: str
    collection_name: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = sanitize_metadata(payload["metadata"])
        return payload


@dataclass
class RagInteraction:
    interaction_id: str
    session_id: str
    collection_name: str
    question: str
    answer: str
    citations: list[dict[str, Any]]
    model_name: str
    created_at: str
    expected_output: str | None = None
    task_type: str = "generic"
    usage: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def default_collection_name(raw_name: str, fallback: str = "knowledge_base") -> str:
    name = slugify(raw_name)
    return name.replace("-", "_") or fallback


def default_session_id() -> str:
    return f"rag-session-{slugify(utc_now())}"


def resolve_workspace_path(paths: RagPaths, raw_path: str) -> Path:
    return resolve_path(paths.workspace_root, raw_path)
