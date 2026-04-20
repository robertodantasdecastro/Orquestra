from __future__ import annotations

from fastapi.testclient import TestClient

from orquestra_ai.app import create_app
from orquestra_ai.config import load_settings


class FakeTrainPlaneClient:
    def __init__(self) -> None:
        self.base_models: list[dict[str, object]] = []
        self.dataset_bundles: list[dict[str, object]] = []
        self.runs: list[dict[str, object]] = []
        self.artifacts: list[dict[str, object]] = []
        self.evaluations: list[dict[str, object]] = []
        self.comparisons: list[dict[str, object]] = []

    def health(self) -> dict[str, object]:
        return {"ok": True, "app": "Orquestra Train Plane"}

    def list_base_models(self) -> list[dict[str, object]]:
        return list(self.base_models)

    def init_base_model_upload(self, payload: dict[str, object]) -> dict[str, object]:
        return {"upload_id": "upload-1", "payload": payload}

    def complete_base_model_upload(self, payload: dict[str, object]) -> dict[str, object]:
        item = {
            "id": "base-model-1",
            "name": "Meta-Llama-3.1-8B-Instruct",
            "source_kind": "huggingface_ref",
            "source_ref": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "storage_uri": payload.get("storage_uri", "s3://trainplane/base-models/model"),
            "size_bytes": 0,
            "checksum_sha256": "",
            "format": "huggingface",
            "status": "ready",
            "metadata": payload.get("metadata", {}),
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
        }
        self.base_models = [item]
        return item

    def list_dataset_bundles(self) -> list[dict[str, object]]:
        return list(self.dataset_bundles)

    def create_dataset_bundle(self, payload: dict[str, object]) -> dict[str, object]:
        item = {
            "id": "dataset-1",
            "project_slug": payload.get("project_slug", "orquestra-lab"),
            "name": payload.get("name", "dataset-bundle"),
            "source": payload.get("source", "orquestra_local"),
            "storage_uri": "s3://trainplane/datasets/dataset-1",
            "record_count": len(payload.get("records", [])),
            "stats": {"records": len(payload.get("records", []))},
            "schema_version": "orquestra-trainplane-v1",
            "metadata": payload.get("metadata", {}),
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
        }
        self.dataset_bundles = [item]
        return item

    def list_runs(self) -> list[dict[str, object]]:
        return list(self.runs)

    def create_run(self, payload: dict[str, object]) -> dict[str, object]:
        artifact = {
            "id": "artifact-1",
            "run_id": "remote-run-1",
            "name": "research-adapter-run-adapter",
            "artifact_type": "adapter",
            "base_model_name": "Meta-Llama-3.1-8B-Instruct",
            "storage_uri": "s3://trainplane/artifacts/research-adapter-run-adapter",
            "format": "adapter-only",
            "status": "ready",
            "benchmark": {"correctness": 0.84, "faithfulness": 0.82},
            "serving_endpoint": {"mode": "simulated"},
            "metadata": {},
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
        }
        run = {
            "id": "remote-run-1",
            "project_slug": payload.get("project_slug", "orquestra-lab"),
            "name": payload.get("name", "research-adapter-run"),
            "base_model_id": payload.get("base_model_id", "base-model-1"),
            "dataset_bundle_id": payload.get("dataset_bundle_id", "dataset-1"),
            "status": "running",
            "summary": payload.get("summary", ""),
            "profile": payload.get("training_profile", {}),
            "logs_path": "/tmp/trainplane-run.log",
            "artifact_id": artifact["id"],
            "output": {},
            "current_step": 2,
            "total_steps": 6,
            "cancel_requested": False,
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
            "started_at": "2026-04-20T00:00:00Z",
            "finished_at": None,
            "metrics": [],
            "checkpoints": [],
            "artifact": artifact,
        }
        self.runs = [run]
        self.artifacts = [artifact]
        return run

    def get_run(self, run_id: str) -> dict[str, object]:
        assert run_id == "remote-run-1"
        return self.runs[0]

    def cancel_run(self, run_id: str) -> dict[str, object]:
        assert run_id == "remote-run-1"
        self.runs[0] = {**self.runs[0], "status": "cancelled", "cancel_requested": True}
        return self.runs[0]

    def list_evaluations(self) -> list[dict[str, object]]:
        return list(self.evaluations)

    def create_evaluation(self, payload: dict[str, object]) -> dict[str, object]:
        item = {
            "id": "evaluation-1",
            "candidate_artifact_id": payload.get("candidate_artifact_id", "artifact-1"),
            "baseline_mode": payload.get("baseline_mode", "trainplane_artifact"),
            "baseline_ref": payload.get("baseline_ref", "baseline-1"),
            "suite_name": payload.get("suite_name", "suite"),
            "status": "succeeded",
            "summary_scores": {"correctness": 0.84},
            "results": payload.get("cases", []),
            "metadata": payload.get("metadata", {}),
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
        }
        self.evaluations = [item]
        return item

    def list_comparisons(self) -> list[dict[str, object]]:
        return list(self.comparisons)

    def create_comparison(self, payload: dict[str, object]) -> dict[str, object]:
        item = {
            "id": "comparison-1",
            "candidate_artifact_id": payload.get("candidate_artifact_id", "artifact-1"),
            "baseline_mode": payload.get("baseline_mode", "trainplane_artifact"),
            "baseline_ref": payload.get("baseline_ref", "baseline-1"),
            "prompt_set_name": payload.get("prompt_set_name", "compare"),
            "status": "succeeded",
            "summary_scores": {"faithfulness": 0.82},
            "cases": payload.get("cases", []),
            "metadata": payload.get("metadata", {}),
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
        }
        self.comparisons = [item]
        return item

    def list_artifacts(self) -> list[dict[str, object]]:
        return list(self.artifacts)

    def merge_artifact(self, artifact_id: str) -> dict[str, object]:
        assert artifact_id == "artifact-1"
        merged = {**self.artifacts[0], "id": "artifact-merged-1", "name": "research-adapter-run-merged", "format": "merged-full"}
        self.artifacts = [merged, *self.artifacts]
        return merged

    def promote_artifact(self, artifact_id: str) -> dict[str, object]:
        assert artifact_id in {"artifact-1", "artifact-merged-1"}
        promoted = {**self.artifacts[0], "status": "promoted"}
        self.artifacts[0] = promoted
        return promoted

    def stream_url(self, run_id: str) -> str:
        return f"http://127.0.0.1:8818/api/training-runs/{run_id}/events?token=fake"


def test_trainplane_proxy_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("ORQUESTRA_DATABASE_URL", f"sqlite:///{tmp_path / 'orquestra.db'}")
    monkeypatch.setenv("ORQUESTRA_QDRANT_PATH", str(tmp_path / "qdrant"))
    monkeypatch.setenv("ORQUESTRA_DISABLE_KEYCHAIN", "1")
    monkeypatch.setenv("ORQUESTRA_TRAINPLANE_TOKEN_FILE", str(tmp_path / "trainplane.token"))
    app = create_app(load_settings())
    fake_client = FakeTrainPlaneClient()
    app.state.trainplane_client_builder = lambda session: fake_client

    with TestClient(app) as client:
        config = client.put(
            "/api/remote/trainplane/config",
            json={
                "base_url": "http://127.0.0.1:8818",
                "token": "fake-token",
                "region": "us-east-1",
                "instance_id": "i-123456789",
                "bucket": "orquestra-trainplane",
                "ssm_enabled": True,
                "default_training_profile": {"execution_mode": "qlora", "max_steps": 6},
                "default_serving_profile": {"engine": "vllm"},
            },
        )
        assert config.status_code == 200, config.text
        assert config.json()["token_configured"] is True

        projects = client.get("/api/projects")
        assert projects.status_code == 200, projects.text
        project_id = projects.json()[0]["id"]

        training_candidate = client.post(
            "/api/memory/training-candidates",
            json={
                "project_id": project_id,
                "source": "manual",
                "instruction": "Explique o objetivo do Orquestra.",
                "context": "Control plane local-first.",
                "response": "Operar memória, RAG e execução.",
                "approved": True,
            },
        )
        assert training_candidate.status_code == 200, training_candidate.text

        health = client.post("/api/remote/trainplane/test-connection")
        assert health.status_code == 200, health.text
        assert health.json()["ok"] is True

        base_model = client.post(
            "/api/remote/trainplane/sync/base-model",
            json={
                "project_id": project_id,
                "name": "Meta-Llama-3.1-8B-Instruct",
                "source_kind": "huggingface_ref",
                "source_ref": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            },
        )
        assert base_model.status_code == 200, base_model.text
        assert base_model.json()["name"] == "Meta-Llama-3.1-8B-Instruct"

        dataset_bundle = client.post(
            "/api/remote/trainplane/sync/dataset-bundle",
            json={
                "project_id": project_id,
                "project_slug": "orquestra-lab",
                "name": "approved-memory-bundle",
                "approved_only": True,
                "max_records": 20,
            },
        )
        assert dataset_bundle.status_code == 200, dataset_bundle.text
        assert dataset_bundle.json()["record_count"] == 1

        run = client.post(
            "/api/remote/trainplane/runs",
            json={
                "project_id": project_id,
                "project_slug": "orquestra-lab",
                "name": "research-adapter-run",
                "base_model_id": "base-model-1",
                "dataset_bundle_id": "dataset-1",
                "summary": "Treino remoto de validação.",
                "training_profile": {"execution_mode": "qlora", "max_steps": 6},
            },
        )
        assert run.status_code == 200, run.text
        assert run.json()["mirrored_job_id"]

        run_details = client.get(f"/api/remote/trainplane/runs/{run.json()['id']}", params={"project_id": project_id})
        assert run_details.status_code == 200, run_details.text
        assert run_details.json()["mirrored_artifact_id"]

        artifacts = client.get("/api/remote/trainplane/artifacts", params={"project_id": project_id})
        assert artifacts.status_code == 200, artifacts.text
        assert artifacts.json()[0]["mirrored_artifact_id"]

        evaluation = client.post(
            "/api/remote/trainplane/evaluations",
            json={
                "project_id": project_id,
                "candidate_artifact_id": "artifact-1",
                "baseline_mode": "trainplane_artifact",
                "baseline_ref": "baseline-1",
                "suite_name": "orquestra-eval-lab",
                "cases": [{"prompt": "Qual é o objetivo do Orquestra?", "baseline_output": "Resposta baseline."}],
            },
        )
        assert evaluation.status_code == 200, evaluation.text
        assert evaluation.json()["summary_scores"]["correctness"] == 0.84

        comparison = client.post(
            "/api/remote/trainplane/comparisons",
            json={
                "project_id": project_id,
                "candidate_artifact_id": "artifact-1",
                "baseline_mode": "trainplane_artifact",
                "baseline_ref": "baseline-1",
                "prompt_set_name": "orquestra-compare-lab",
                "cases": [{"prompt": "Resuma o projeto.", "baseline_output": "Resumo baseline."}],
            },
        )
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["summary_scores"]["faithfulness"] == 0.82
