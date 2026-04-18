from __future__ import annotations

import statistics
import os
import subprocess
from dataclasses import dataclass
from typing import Any

from training.local.evaluation import (
    correctness_score,
    document_relevance_score,
    faithfulness_score,
    publish_to_phoenix,
    EvaluationSample,
)

from .common import RagPaths, utc_now, write_json

try:
    from langfuse import Langfuse
except Exception:  # pragma: no cover - ambiente opcional
    Langfuse = None  # type: ignore[assignment]


UNSAFE_PATTERNS = (
    "rm -rf /",
    "sudo rm -rf",
    "mkfs",
    "dd if=",
    "curl | sh",
    "wget | sh",
    "chmod 777",
)


@dataclass
class RagEvalSample:
    sample_id: str
    task_type: str
    question: str
    answer: str
    expected_output: str
    context: str
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def normalize_shell_command(value: str) -> str:
    return " ".join(value.strip().split())


def is_unsafe_command(value: str) -> bool:
    lowered = value.lower()
    return any(pattern in lowered for pattern in UNSAFE_PATTERNS)


def script_structure_score(answer: str) -> float:
    checks = [
        answer.startswith("#!/"),
        "set -euo pipefail" in answer,
        any(token in answer for token in ("if ", "for ", "while ", "case ")),
        "\n" in answer,
    ]
    return round(sum(1 for item in checks if item) / len(checks), 4)


def domain_scores(sample: RagEvalSample) -> dict[str, float]:
    answer = sample.answer.strip()
    expected = sample.expected_output.strip()
    exact_match = float(answer == expected) if sample.task_type == "shell_command_generation" else 0.0
    normalized_match = (
        float(normalize_shell_command(answer) == normalize_shell_command(expected))
        if sample.task_type == "shell_command_generation"
        else 0.0
    )
    unsafe_rate = float(is_unsafe_command(answer))
    return {
        "shell_exact_match": exact_match,
        "shell_normalized_match": normalized_match,
        "unsafe_command": unsafe_rate,
        "script_structure": script_structure_score(answer) if sample.task_type == "bash_script_editing" else 0.0,
        "python_fix_correctness": correctness_score(expected, answer) if sample.task_type == "python_fix_and_refactor" else 0.0,
        "command_explanation_correctness": correctness_score(expected, answer) if sample.task_type == "command_explanation" else 0.0,
    }


def aggregate_scores(samples: list[RagEvalSample]) -> dict[str, float]:
    if not samples:
        return {}

    per_sample = [per_sample_metrics(sample) for sample in samples]
    latencies: list[float] = []
    total_tokens: list[int] = []
    for sample in samples:
        latencies.append(sample.latency_seconds)
        total_tokens.append(sample.total_tokens)

    def avg(key: str, source: list[dict[str, float]]) -> float:
        return round(sum(item[key] for item in source) / len(source), 4)

    p95_index = max(int(len(latencies) * 0.95) - 1, 0)
    ordered_latencies = sorted(latencies)
    return {
        "faithfulness": avg("faithfulness", per_sample),
        "document_relevance": avg("document_relevance", per_sample),
        "correctness": avg("correctness", per_sample),
        "shell_exact_match_rate": avg("shell_exact_match", per_sample),
        "shell_normalized_match_rate": avg("shell_normalized_match", per_sample),
        "unsafe_command_rate": avg("unsafe_command", per_sample),
        "script_structure_score": avg("script_structure", per_sample),
        "python_fix_correctness": avg("python_fix_correctness", per_sample),
        "command_explanation_correctness": avg("command_explanation_correctness", per_sample),
        "latency_avg": round(statistics.mean(latencies), 4),
        "latency_p95": round(ordered_latencies[p95_index], 4),
        "tokens_avg": round(statistics.mean(total_tokens), 4),
        "cost": 0.0,
    }


def per_sample_metrics(sample: RagEvalSample) -> dict[str, float]:
    general = {
        "faithfulness": faithfulness_score(sample.context, sample.answer, sample.expected_output),
        "document_relevance": document_relevance_score(sample.question, sample.context),
        "correctness": correctness_score(sample.expected_output, sample.answer),
    }
    return general | domain_scores(sample)


def publish_rag_scores_to_langfuse(
    *,
    client: Langfuse | None,
    run_id: str,
    model_name: str,
    sample: RagEvalSample,
    metrics: dict[str, float],
) -> dict[str, Any] | None:
    if client is None:
        return None

    with client.start_as_current_span(
        name="rag_query",
        input={"run_id": run_id, "sample_id": sample.sample_id, "question": sample.question},
        metadata={"task_type": sample.task_type, "model_name": model_name},
    ) as span:
        with client.start_as_current_generation(
            name="rag_generation",
            input=sample.question,
            output=sample.answer,
            model=model_name,
            usage_details={
                "input": sample.prompt_tokens,
                "output": sample.completion_tokens,
                "total": sample.total_tokens,
            },
            cost_details={"total": 0.0},
            metadata={"task_type": sample.task_type, "latency_seconds": sample.latency_seconds},
        ):
            pass

        trace_id = getattr(span, "trace_id", None)
        observation_id = getattr(span, "id", None)
        for key, value in metrics.items():
            client.create_score(
                name=key,
                value=float(value),
                trace_id=trace_id,
                observation_id=observation_id,
                data_type="NUMERIC",
            )
        return {"trace_id": trace_id, "observation_id": observation_id}


def write_evaluation_report(
    paths: RagPaths,
    *,
    report_id: str,
    model_name: str,
    samples: list[RagEvalSample],
    aggregate: dict[str, float],
    langfuse_status: dict[str, Any],
    phoenix_status: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "report_id": report_id,
        "created_at": utc_now(),
        "model_name": model_name,
        "aggregate_scores": aggregate,
        "langfuse": langfuse_status,
        "phoenix": phoenix_status,
        "samples": [
            {
                "sample_id": item.sample_id,
                "task_type": item.task_type,
                "question": item.question,
                "answer": item.answer,
                "expected_output": item.expected_output,
                "context": item.context,
                "latency_seconds": item.latency_seconds,
                "prompt_tokens": item.prompt_tokens,
                "completion_tokens": item.completion_tokens,
                "total_tokens": item.total_tokens,
            }
            for item in samples
        ],
    }
    write_json(paths.evaluations_dir / f"{report_id}.json", payload)
    return payload


def publish_rag_observability(
    *,
    paths: RagPaths,
    report_id: str,
    model_name: str,
    samples: list[RagEvalSample],
) -> tuple[dict[str, Any], dict[str, Any]]:
    langfuse_client, phoenix_client = current_observability_clients()
    langfuse_status: dict[str, Any] = {
        "enabled": bool(langfuse_client),
        "published_samples": 0,
        "reason": "ok" if langfuse_client else "disabled_or_not_configured",
    }
    per_sample_scores = [per_sample_metrics(sample) for sample in samples]
    for sample, metrics in zip(samples, per_sample_scores, strict=True):
        if langfuse_client is None:
            continue
        publish_rag_scores_to_langfuse(
            client=langfuse_client,
            run_id=report_id,
            model_name=model_name,
            sample=sample,
            metrics=metrics,
        )
        langfuse_status["published_samples"] = int(langfuse_status["published_samples"]) + 1
    if langfuse_client is not None:
        langfuse_client.flush()

    phoenix_payload: list[EvaluationSample] = [
        EvaluationSample(
            sample_id=item.sample_id,
            prompt=item.question,
            generated_output=item.answer,
            expected_output=item.expected_output,
            context=item.context,
            latency_seconds=item.latency_seconds,
            prompt_tokens=item.prompt_tokens,
            completion_tokens=item.completion_tokens,
            total_tokens=item.total_tokens,
        )
        for item in samples
    ]
    phoenix_status: dict[str, Any] = {
        "enabled": bool(phoenix_client),
        "reason": "ok" if phoenix_client else "disabled_or_not_running",
    }
    published = publish_to_phoenix(
        phoenix_client=phoenix_client,
        run_id=report_id,
        samples=phoenix_payload,
        per_sample_scores=per_sample_scores,
        model_id=model_name,
    )
    if published:
        phoenix_status.update(published)
    return langfuse_status, phoenix_status


def current_observability_clients() -> tuple[Any | None, Any | None]:
    return load_langfuse_client(), load_phoenix_client()


def load_langfuse_client() -> Any | None:
    if Langfuse is None:
        return None
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY") or os.getenv("LANGFUSE_INIT_PROJECT_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY") or os.getenv("LANGFUSE_INIT_PROJECT_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000"))
    if not public_key or not secret_key:
        return None
    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def load_phoenix_client() -> Any | None:
    try:
        import phoenix
    except Exception:  # pragma: no cover - ambiente opcional
        return None

    host = os.getenv("PHOENIX_HOST", "127.0.0.1")
    port = int(os.getenv("PHOENIX_PORT", "6006"))
    probe = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"http://{host}:{port}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or probe.stdout.strip() not in {"200", "302", "405"}:
        return None
    return phoenix.Client(endpoint=f"http://{host}:{port}")
