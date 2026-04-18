from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import compare_models, run_model_benchmark
from .common import RagPaths, default_collection_name, default_session_id, resolve_workspace_path
from .export import export_interactions_to_training_dataset
from .graph import RagWorkflow
from .ingestion import ingest_local_directory, ingest_security_csv, ingest_web_manifest
from .memory import MemoryManager


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def command_status(args: argparse.Namespace) -> int:
    del args
    paths = RagPaths.load(workspace_root())
    paths.ensure()
    memory = MemoryManager(paths)
    payload = memory.snapshot() | {
        "experiments_root": str(paths.experiments_root),
        "datasets_export_dir": str(paths.datasets_export_dir),
        "benchmark_dataset": str(paths.benchmark_dataset),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_bootstrap_demo(args: argparse.Namespace) -> int:
    del args
    paths = RagPaths.load(workspace_root())
    local_report = ingest_local_directory(
        paths,
        paths.samples_dir / "knowledge",
        collection_name="knowledge_base",
    )
    csv_report = ingest_security_csv(
        paths,
        paths.samples_dir / "security" / "security_rules.csv",
        collection_name="security_base",
    )
    print(json.dumps({"knowledge": local_report, "security": csv_report}, indent=2, ensure_ascii=False))
    return 0


def command_ingest_local(args: argparse.Namespace) -> int:
    paths = RagPaths.load(workspace_root())
    source_dir = resolve_workspace_path(paths, args.source_dir)
    payload = ingest_local_directory(
        paths,
        source_dir,
        collection_name=args.collection,
        glob_pattern=args.glob,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_ingest_csv(args: argparse.Namespace) -> int:
    paths = RagPaths.load(workspace_root())
    csv_path = resolve_workspace_path(paths, args.csv_path)
    payload = ingest_security_csv(paths, csv_path, collection_name=args.collection)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_ingest_web(args: argparse.Namespace) -> int:
    paths = RagPaths.load(workspace_root())
    manifest_path = resolve_workspace_path(paths, args.manifest)
    payload = ingest_web_manifest(paths, manifest_path, collection_name=args.collection)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_query(args: argparse.Namespace) -> int:
    paths = RagPaths.load(workspace_root())
    workflow = RagWorkflow(
        paths,
        default_collection=args.collection,
        security_collection=args.security_collection,
        mock_llm=args.mock_llm,
        provider_id=args.provider,
    )
    payload = workflow.invoke(
        question=args.question,
        session_id=args.session_id or default_session_id(),
        collection_name=args.collection,
        provider_id=args.provider,
        model_name=args.model,
        expected_output=args.expected_output,
        task_type=args.task_type,
        remember=args.remember,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_export_training(args: argparse.Namespace) -> int:
    paths = RagPaths.load(workspace_root())
    payload = export_interactions_to_training_dataset(
        paths,
        session_id=args.session_id,
        min_correctness=args.min_correctness,
        min_faithfulness=args.min_faithfulness,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_benchmark_model(args: argparse.Namespace) -> int:
    paths = RagPaths.load(workspace_root())
    dataset_path = resolve_workspace_path(paths, args.dataset or str(paths.benchmark_dataset))
    payload = run_model_benchmark(
        paths,
        model_name=args.model,
        dataset_path=dataset_path,
        collection_name=args.collection,
        mock_llm=args.mock_llm,
        provider_id=args.provider,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_compare_models(args: argparse.Namespace) -> int:
    paths = RagPaths.load(workspace_root())
    dataset_path = resolve_workspace_path(paths, args.dataset or str(paths.benchmark_dataset))
    payload = compare_models(
        paths,
        baseline_model=args.baseline,
        candidate_model=args.candidate,
        dataset_path=dataset_path,
        collection_name=args.collection,
        mock_llm=args.mock_llm,
        provider_id=args.provider,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Camada RAG local para Orquestra")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Mostra snapshot do runtime RAG")
    status_parser.set_defaults(func=command_status)

    bootstrap_parser = subparsers.add_parser("bootstrap-demo", help="Ingere os samples locais de conhecimento e seguranca")
    bootstrap_parser.set_defaults(func=command_bootstrap_demo)

    ingest_local_parser = subparsers.add_parser("ingest-local", help="Indexa arquivos locais na base vetorial")
    ingest_local_parser.add_argument("--source-dir", required=True, help="Diretorio local com arquivos de conhecimento")
    ingest_local_parser.add_argument("--collection", default="knowledge_base", help="Nome da colecao")
    ingest_local_parser.add_argument("--glob", default="**/*", help="Padrao glob para arquivos")
    ingest_local_parser.set_defaults(func=command_ingest_local)

    ingest_csv_parser = subparsers.add_parser("ingest-csv", help="Indexa um CSV de regras de seguranca")
    ingest_csv_parser.add_argument("--csv-path", required=True, help="Arquivo CSV de seguranca")
    ingest_csv_parser.add_argument("--collection", default="security_base", help="Nome da colecao")
    ingest_csv_parser.set_defaults(func=command_ingest_csv)

    ingest_web_parser = subparsers.add_parser("ingest-web", help="Indexa fontes web a partir de um manifesto")
    ingest_web_parser.add_argument("--manifest", required=True, help="Manifesto JSON de coleta web")
    ingest_web_parser.add_argument("--collection", help="Sobrescreve a colecao final")
    ingest_web_parser.set_defaults(func=command_ingest_web)

    query_parser = subparsers.add_parser("query", help="Executa um fluxo RAG com LangGraph")
    query_parser.add_argument("--question", required=True, help="Pergunta para o fluxo RAG")
    query_parser.add_argument("--session-id", help="Sessao de memoria")
    query_parser.add_argument("--collection", default="knowledge_base", help="Colecao principal")
    query_parser.add_argument("--security-collection", default="security_base", help="Colecao de seguranca")
    query_parser.add_argument("--model", help="Modelo servido pelo LM Studio")
    query_parser.add_argument("--provider", default=None, help="Provider do gateway Orquestra (lmstudio, openai, anthropic, deepseek, ollama)")
    query_parser.add_argument("--task-type", default="generic", help="Tipo de tarefa para avaliacao")
    query_parser.add_argument("--expected-output", default="", help="Resposta esperada opcional")
    query_parser.add_argument("--remember", action="store_true", help="Promove a resposta como memoria episodica")
    query_parser.add_argument("--mock-llm", action="store_true", help="Nao usa LM Studio; responde com fallback do contexto")
    query_parser.set_defaults(func=command_query)

    export_parser = subparsers.add_parser("export-training", help="Exporta interacoes do RAG para dataset de treino")
    export_parser.add_argument("--session-id", help="Filtra por sessao")
    export_parser.add_argument("--min-correctness", type=float, default=0.3, help="Minimo de correctness")
    export_parser.add_argument("--min-faithfulness", type=float, default=0.2, help="Minimo de faithfulness")
    export_parser.set_defaults(func=command_export_training)

    benchmark_parser = subparsers.add_parser("benchmark-model", help="Roda benchmark de um modelo no pipeline RAG")
    benchmark_parser.add_argument("--model", required=True, help="Modelo do LM Studio")
    benchmark_parser.add_argument("--dataset", help="Dataset JSONL de benchmark")
    benchmark_parser.add_argument("--collection", default="knowledge_base", help="Colecao principal")
    benchmark_parser.add_argument("--provider", default=None, help="Provider do gateway Orquestra")
    benchmark_parser.add_argument("--mock-llm", action="store_true", help="Nao usa LM Studio")
    benchmark_parser.set_defaults(func=command_benchmark_model)

    compare_parser = subparsers.add_parser("compare-models", help="Compara baseline e candidato no mesmo benchmark")
    compare_parser.add_argument("--baseline", required=True, help="Modelo baseline")
    compare_parser.add_argument("--candidate", required=True, help="Modelo candidato")
    compare_parser.add_argument("--dataset", help="Dataset JSONL de benchmark")
    compare_parser.add_argument("--collection", default="knowledge_base", help="Colecao principal")
    compare_parser.add_argument("--provider", default=None, help="Provider do gateway Orquestra")
    compare_parser.add_argument("--mock-llm", action="store_true", help="Nao usa LM Studio")
    compare_parser.set_defaults(func=command_compare_models)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
