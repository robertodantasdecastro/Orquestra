from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import RagPaths, read_jsonl, slugify, utc_now, write_json
from .evaluation import RagEvalSample, aggregate_scores, publish_rag_observability, write_evaluation_report
from .graph import RagWorkflow


def run_model_benchmark(
    paths: RagPaths,
    *,
    model_name: str,
    dataset_path: Path,
    collection_name: str = "knowledge_base",
    mock_llm: bool = False,
    provider_id: str | None = None,
) -> dict[str, Any]:
    workflow = RagWorkflow(paths, default_collection=collection_name, mock_llm=mock_llm, provider_id=provider_id)
    records = read_jsonl(dataset_path)
    samples: list[RagEvalSample] = []
    attempted = 0
    succeeded = 0
    report_id = f"benchmark-{slugify(model_name)}-{slugify(utc_now())}"
    benchmark_session_id = f"{report_id}-session"

    for record in records:
        attempted += 1
        result = workflow.invoke(
            question=str(record.get("question", "")),
            session_id=benchmark_session_id,
            collection_name=str(record.get("collection_name", collection_name)),
            model_name=model_name,
            expected_output=str(record.get("expected_output", "")),
            task_type=str(record.get("task_type", "generic")),
            remember=False,
            persist_interaction=False,
            publish_observability=False,
        )
        context = "\n\n".join(item["text"] for item in result.get("retrieved_docs", []))
        if str(result.get("answer", "")).strip():
            succeeded += 1
        sample = RagEvalSample(
            sample_id=str(record.get("id", slugify(model_name))),
            task_type=str(record.get("task_type", "generic")),
            question=str(record.get("question", "")),
            answer=str(result.get("answer", "")),
            expected_output=str(record.get("expected_output", "")),
            context=context,
            latency_seconds=float(result.get("latency_seconds", 0.0)),
            prompt_tokens=int(result.get("usage", {}).get("prompt_tokens", 0)),
            completion_tokens=int(result.get("usage", {}).get("completion_tokens", 0)),
            total_tokens=int(result.get("usage", {}).get("total_tokens", 0)),
        )
        samples.append(sample)

    aggregate = aggregate_scores(samples)
    langfuse_status, phoenix_status = publish_rag_observability(
        paths=paths,
        report_id=report_id,
        model_name=model_name,
        samples=samples,
    )
    inference_reference = {
        "request_success_rate": round(succeeded / attempted, 4) if attempted else 0.0,
        "attempted_requests": attempted,
        "successful_requests": succeeded,
        "latency_avg": aggregate.get("latency_avg", 0.0),
        "latency_p95": aggregate.get("latency_p95", 0.0),
        "tokens_avg": aggregate.get("tokens_avg", 0.0),
        "server_stability": "stable" if attempted and succeeded == attempted else "degraded",
    }
    payload = write_evaluation_report(
        paths,
        report_id=report_id,
        model_name=model_name,
        samples=samples,
        aggregate=aggregate,
        langfuse_status=langfuse_status,
        phoenix_status=phoenix_status,
    )
    payload["inference_reference"] = inference_reference
    write_json(paths.evaluations_dir / f"{report_id}.json", payload)
    return payload


def compare_models(
    paths: RagPaths,
    *,
    baseline_model: str,
    candidate_model: str,
    dataset_path: Path,
    collection_name: str = "knowledge_base",
    mock_llm: bool = False,
    provider_id: str | None = None,
) -> dict[str, Any]:
    baseline = run_model_benchmark(
        paths,
        model_name=baseline_model,
        dataset_path=dataset_path,
        collection_name=collection_name,
        mock_llm=mock_llm,
        provider_id=provider_id,
    )
    candidate = run_model_benchmark(
        paths,
        model_name=candidate_model,
        dataset_path=dataset_path,
        collection_name=collection_name,
        mock_llm=mock_llm,
        provider_id=provider_id,
    )
    delta = {
        key: round(candidate["aggregate_scores"].get(key, 0.0) - baseline["aggregate_scores"].get(key, 0.0), 4)
        for key in sorted(set(candidate["aggregate_scores"]) | set(baseline["aggregate_scores"]))
    }
    report = {
        "comparison_id": f"compare-{slugify(baseline_model)}-vs-{slugify(candidate_model)}-{slugify(utc_now())}",
        "created_at": utc_now(),
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "baseline_report": baseline["report_id"],
        "candidate_report": candidate["report_id"],
        "baseline_scores": baseline["aggregate_scores"],
        "candidate_scores": candidate["aggregate_scores"],
        "delta": delta,
    }
    write_json(paths.benchmarks_dir / f"{report['comparison_id']}.json", report)
    return report
