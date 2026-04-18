from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pandas as pd

try:
    import phoenix
    from phoenix import Client as PhoenixClient
    from phoenix.trace.span_evaluations import DocumentEvaluations, SpanEvaluations
    from phoenix.trace.trace_dataset import TraceDataset
except Exception:  # pragma: no cover - ambiente opcional
    phoenix = None  # type: ignore[assignment]
    PhoenixClient = object  # type: ignore[assignment,misc]
    DocumentEvaluations = object  # type: ignore[assignment,misc]
    SpanEvaluations = object  # type: ignore[assignment,misc]
    TraceDataset = object  # type: ignore[assignment,misc]

try:
    from langfuse import Langfuse
except Exception:  # pragma: no cover - ambiente opcional
    Langfuse = object  # type: ignore[assignment,misc]

from .common import RuntimePaths, utc_now


@dataclass
class EvaluationSample:
    sample_id: str
    prompt: str
    generated_output: str
    expected_output: str
    context: str
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def tokenize_words(text: str) -> list[str]:
    return [token for token in text.lower().replace("\n", " ").split() if token]


def overlap_ratio(left: str, right: str) -> float:
    left_tokens = set(tokenize_words(left))
    right_tokens = set(tokenize_words(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), 1)


def correctness_score(expected_output: str, generated_output: str) -> float:
    return round(overlap_ratio(expected_output, generated_output), 4)


def faithfulness_score(context: str, generated_output: str, expected_output: str) -> float:
    baseline = context or expected_output
    return round(overlap_ratio(baseline, generated_output), 4)


def document_relevance_score(prompt: str, context: str) -> float:
    return round(overlap_ratio(prompt, context), 4)


def publish_to_langfuse(
    *,
    langfuse_client: Langfuse | None,
    run_id: str,
    profile_name: str,
    model_id: str,
    sample: EvaluationSample,
    scores: dict[str, float],
) -> dict[str, str] | None:
    if langfuse_client is None:
        return None

    with langfuse_client.start_as_current_span(
        name="local_eval_sample",
        input={
            "run_id": run_id,
            "sample_id": sample.sample_id,
            "prompt": sample.prompt,
            "expected_output": sample.expected_output,
        },
        metadata={
            "profile_name": profile_name,
            "model_id": model_id,
            "context_present": bool(sample.context),
        },
    ) as span:
        with langfuse_client.start_as_current_generation(
            name="local_eval_generation",
            input=sample.prompt,
            output=sample.generated_output,
            model=model_id,
            usage_details={
                "input": sample.prompt_tokens,
                "output": sample.completion_tokens,
                "total": sample.total_tokens,
            },
            cost_details={"total": 0.0},
            metadata={
                "run_id": run_id,
                "sample_id": sample.sample_id,
                "latency_seconds": sample.latency_seconds,
            },
        ) as generation:
            generation.update(output=sample.generated_output)

        trace_id = getattr(span, "trace_id", None)
        observation_id = getattr(span, "id", None)
        langfuse_client.create_score(
            name="faithfulness",
            value=scores["faithfulness"],
            trace_id=trace_id,
            observation_id=observation_id,
            data_type="NUMERIC",
            comment="Score heuristico de aderencia ao contexto.",
        )
        langfuse_client.create_score(
            name="document_relevance",
            value=scores["document_relevance"],
            trace_id=trace_id,
            observation_id=observation_id,
            data_type="NUMERIC",
            comment="Sobreposicao heuristica entre prompt e contexto.",
        )
        langfuse_client.create_score(
            name="correctness",
            value=scores["correctness"],
            trace_id=trace_id,
            observation_id=observation_id,
            data_type="NUMERIC",
            comment="Sobreposicao heuristica entre resposta esperada e gerada.",
        )
        langfuse_client.create_score(
            name="latency",
            value=sample.latency_seconds,
            trace_id=trace_id,
            observation_id=observation_id,
            data_type="NUMERIC",
        )
        langfuse_client.create_score(
            name="token_usage",
            value=float(sample.total_tokens),
            trace_id=trace_id,
            observation_id=observation_id,
            data_type="NUMERIC",
        )
        langfuse_client.create_score(
            name="cost",
            value=0.0,
            trace_id=trace_id,
            observation_id=observation_id,
            data_type="NUMERIC",
        )

        return {
            "trace_id": trace_id or "",
            "observation_id": observation_id or "",
        }


def publish_to_phoenix(
    *,
    phoenix_client: PhoenixClient | None,
    run_id: str,
    samples: list[EvaluationSample],
    per_sample_scores: list[dict[str, float]],
    model_id: str,
) -> dict[str, str] | None:
    if phoenix_client is None or not samples:
        return None

    rows: list[dict[str, object]] = []
    span_rows: list[dict[str, object]] = []
    document_rows: list[dict[str, object]] = []
    trace_dataset_name = f"local-train-{run_id}"
    start = datetime.now(timezone.utc)

    for index, (sample, scores) in enumerate(zip(samples, per_sample_scores, strict=True)):
        span_id = uuid4().hex[:16]
        trace_id = uuid4().hex
        row_start = start + timedelta(seconds=index * 2)
        row_end = row_start + timedelta(seconds=max(sample.latency_seconds, 0.01))
        rows.append(
            {
                "name": "local_eval_generation",
                "span_kind": "LLM",
                "parent_id": None,
                "start_time": row_start,
                "end_time": row_end,
                "status_code": "OK",
                "status_message": "",
                "context.span_id": span_id,
                "context.trace_id": trace_id,
                "attributes.input.value": sample.prompt,
                "attributes.output.value": sample.generated_output,
                "attributes.llm.model_name": model_id,
                "attributes.metadata.run_id": run_id,
                "attributes.metadata.sample_id": sample.sample_id,
            }
        )
        span_rows.append(
            {
                "span_id": span_id,
                "score": scores["faithfulness"],
                "label": "faithful" if scores["faithfulness"] >= 0.5 else "weak",
                "explanation": "Score heuristico de aderencia ao contexto.",
            }
        )
        span_rows.append(
            {
                "span_id": span_id,
                "score": scores["correctness"],
                "label": "correct" if scores["correctness"] >= 0.5 else "partial",
                "explanation": "Score heuristico de aderencia a resposta esperada.",
            }
        )
        document_rows.append(
            {
                "span_id": span_id,
                "document_position": 0,
                "score": scores["document_relevance"],
                "label": "relevant" if scores["document_relevance"] >= 0.5 else "weak",
                "explanation": "Score heuristico de relevancia entre prompt e contexto.",
            }
        )

    trace_dataset = TraceDataset(
        dataframe=pd.DataFrame(rows),
        name=trace_dataset_name,
        evaluations=[
            SpanEvaluations(
                eval_name="faithfulness",
                dataframe=pd.DataFrame([row for row in span_rows if row["explanation"].startswith("Score heuristico de aderencia ao contexto")]),
            ),
            SpanEvaluations(
                eval_name="correctness",
                dataframe=pd.DataFrame([row for row in span_rows if row["explanation"].startswith("Score heuristico de aderencia a resposta esperada")]),
            ),
            DocumentEvaluations(
                eval_name="document_relevance",
                dataframe=pd.DataFrame(document_rows),
            ),
        ],
    )
    phoenix_client.log_traces(trace_dataset, project_name=trace_dataset_name)
    return {"project_name": trace_dataset_name, "trace_dataset_name": trace_dataset_name}


def summarize_scores(per_sample_scores: list[dict[str, float]], samples: list[EvaluationSample]) -> dict[str, float]:
    if not per_sample_scores:
        return {}
    size = len(per_sample_scores)
    return {
        "faithfulness": round(sum(item["faithfulness"] for item in per_sample_scores) / size, 4),
        "document_relevance": round(sum(item["document_relevance"] for item in per_sample_scores) / size, 4),
        "correctness": round(sum(item["correctness"] for item in per_sample_scores) / size, 4),
        "latency": round(sum(item.latency_seconds for item in samples) / size, 4),
        "token_usage": round(sum(item.total_tokens for item in samples) / size, 4),
        "cost": 0.0,
    }


def report_payload(
    *,
    run_id: str,
    model_id: str,
    samples: list[EvaluationSample],
    per_sample_scores: list[dict[str, float]],
    aggregate_scores: dict[str, float],
    langfuse_status: dict[str, object],
    phoenix_status: dict[str, object],
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "model_id": model_id,
        "created_at": utc_now(),
        "aggregate_scores": aggregate_scores,
        "langfuse": langfuse_status,
        "phoenix": phoenix_status,
        "samples": [
            {
                "sample_id": sample.sample_id,
                "prompt": sample.prompt,
                "generated_output": sample.generated_output,
                "expected_output": sample.expected_output,
                "context": sample.context,
                "latency_seconds": sample.latency_seconds,
                "prompt_tokens": sample.prompt_tokens,
                "completion_tokens": sample.completion_tokens,
                "total_tokens": sample.total_tokens,
                "scores": scores,
            }
            for sample, scores in zip(samples, per_sample_scores, strict=True)
        ],
    }
