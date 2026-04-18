from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import RagPaths, append_jsonl, read_jsonl, slugify, utc_now, write_json


def export_interactions_to_training_dataset(
    paths: RagPaths,
    *,
    session_id: str | None = None,
    min_correctness: float = 0.3,
    min_faithfulness: float = 0.2,
) -> dict[str, Any]:
    paths.ensure()
    interaction_files = sorted(paths.session_memory_dir.glob("*.jsonl"))
    selected_records: list[dict[str, Any]] = []

    for file_path in interaction_files:
        if session_id and file_path.stem != slugify(session_id):
            continue
        for item in read_jsonl(file_path):
            evaluation = item.get("evaluation") or {}
            if evaluation:
                if evaluation.get("correctness", 0.0) < min_correctness:
                    continue
                if evaluation.get("faithfulness", 0.0) < min_faithfulness:
                    continue
            answer = str(item.get("answer", "")).strip()
            if not answer:
                continue
            context_lines: list[str] = []
            for citation in item.get("citations", []):
                title = citation.get("title") or citation.get("source") or citation.get("channel", "source")
                if title:
                    context_lines.append(str(title))
            selected_records.append(
                {
                    "id": item.get("interaction_id", slugify(utc_now())),
                    "instruction": item.get("question", ""),
                    "input": "",
                    "context": "\n".join(context_lines),
                    "output": answer,
                    "task_type": item.get("task_type", "generic"),
                    "source_collection": item.get("collection_name", ""),
                    "source_session": item.get("session_id", ""),
                    "source_pipeline": "rag",
                    "rag_evaluation": evaluation,
                }
            )

    export_id = f"rag-export-{slugify(session_id or 'all')}-{slugify(utc_now())}"
    dataset_path = paths.datasets_export_dir / f"{export_id}.jsonl"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    with dataset_path.open("w", encoding="utf-8") as handle:
        for item in selected_records:
            handle.write(__import__("json").dumps(item, ensure_ascii=False) + "\n")

    report = {
        "export_id": export_id,
        "created_at": utc_now(),
        "session_id": session_id,
        "records": len(selected_records),
        "dataset_path": str(dataset_path),
        "min_correctness": min_correctness,
        "min_faithfulness": min_faithfulness,
    }
    write_json(paths.exports_dir / f"{export_id}.json", report)
    append_jsonl(paths.experiments_root / "exports_index.jsonl", report)
    return report
