from __future__ import annotations

import time

from fastapi.testclient import TestClient

from orquestra_trainplane.app import create_app
from orquestra_trainplane.config import load_settings
from orquestra_trainplane.services import generate_totp_code


def _bootstrap_and_login(client: TestClient) -> str:
    bootstrap = client.post("/api/auth/bootstrap", json={"username": "admin", "password": "trainplane-secret"})
    assert bootstrap.status_code == 200, bootstrap.text
    secret = bootstrap.json()["totp_secret"]

    login = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "trainplane-secret",
            "totp_code": generate_totp_code(secret),
            "label": "pytest",
        },
    )
    assert login.status_code == 200, login.text
    return str(login.json()["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_trainplane_remote_happy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAINPLANE_STORAGE_ROOT", str(tmp_path / "trainplane-storage"))
    monkeypatch.setenv("TRAINPLANE_DATABASE_URL", f"sqlite:///{tmp_path / 'trainplane.db'}")
    monkeypatch.setenv("TRAINPLANE_PUBLIC_BASE_URL", "http://127.0.0.1:8818")
    monkeypatch.setenv("TRAINPLANE_RUN_TICK_SECONDS", "0.01")
    app = create_app(load_settings())

    with TestClient(app) as client:
        token = _bootstrap_and_login(client)
        headers = _auth_headers(token)

        init_upload = client.post(
            "/api/base-models/upload/init",
            headers=headers,
            json={
                "name": "Meta-Llama-3.1-8B-Instruct",
                "source_kind": "huggingface_ref",
                "source_ref": "meta-llama/Meta-Llama-3.1-8B-Instruct",
                "format": "huggingface",
            },
        )
        assert init_upload.status_code == 200, init_upload.text

        base_model = client.post(
            "/api/base-models/upload/complete",
            headers=headers,
            json={
                "upload_id": init_upload.json()["upload_id"],
                "storage_uri": "s3://trainplane/base-models/meta-llama-3.1-8b-instruct",
            },
        )
        assert base_model.status_code == 200, base_model.text
        base_model_id = base_model.json()["id"]

        dataset_bundle = client.post(
            "/api/dataset-bundles",
            headers=headers,
            json={
                "project_slug": "orquestra-lab",
                "name": "approved-memory-bundle",
                "records": [
                    {
                        "instruction": "Explique o objetivo do projeto.",
                        "context": "Control plane local-first.",
                        "response": "Operar memória, RAG e execução multi-step.",
                    }
                ],
            },
        )
        assert dataset_bundle.status_code == 200, dataset_bundle.text
        dataset_bundle_id = dataset_bundle.json()["id"]

        run = client.post(
            "/api/training-runs",
            headers=headers,
            json={
                "project_slug": "orquestra-lab",
                "name": "research-adapter-run",
                "base_model_id": base_model_id,
                "dataset_bundle_id": dataset_bundle_id,
                "summary": "Treino adapter-first de validação.",
                "training_profile": {"execution_mode": "qlora", "max_steps": 4},
            },
        )
        assert run.status_code == 200, run.text
        run_id = run.json()["id"]

        run_payload = run.json()
        for _ in range(120):
            current = client.get(f"/api/training-runs/{run_id}", headers=headers)
            assert current.status_code == 200, current.text
            run_payload = current.json()
            if run_payload["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)

        assert run_payload["status"] == "succeeded", run_payload
        assert run_payload["artifact"] is not None, run_payload
        assert len(run_payload["metrics"]) >= 1, run_payload
        assert len(run_payload["checkpoints"]) >= 1, run_payload

        artifact_id = run_payload["artifact"]["id"]
        evaluations = client.post(
            "/api/evaluation-runs",
            headers=headers,
            json={
                "candidate_artifact_id": artifact_id,
                "baseline_mode": "lmstudio_local",
                "baseline_ref": "lmstudio/ministral",
                "suite_name": "orquestra-eval-lab",
                "cases": [{"prompt": "Qual é o objetivo do projeto?", "expected_output": "Operar memória, RAG e execução multi-step."}],
            },
        )
        assert evaluations.status_code == 200, evaluations.text
        assert evaluations.json()["summary_scores"]["correctness"] >= 0.8

        comparisons = client.post(
            "/api/comparison-runs",
            headers=headers,
            json={
                "candidate_artifact_id": artifact_id,
                "baseline_mode": "lmstudio_local",
                "baseline_ref": "lmstudio/ministral",
                "prompt_set_name": "orquestra-compare-lab",
                "cases": [{"prompt": "Resuma o Orquestra.", "baseline_output": "Resumo baseline."}],
            },
        )
        assert comparisons.status_code == 200, comparisons.text
        assert comparisons.json()["summary_scores"]["faithfulness"] >= 0.7


def test_trainplane_remote_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAINPLANE_STORAGE_ROOT", str(tmp_path / "trainplane-storage"))
    monkeypatch.setenv("TRAINPLANE_DATABASE_URL", f"sqlite:///{tmp_path / 'trainplane.db'}")
    monkeypatch.setenv("TRAINPLANE_PUBLIC_BASE_URL", "http://127.0.0.1:8818")
    monkeypatch.setenv("TRAINPLANE_RUN_TICK_SECONDS", "0.02")
    app = create_app(load_settings())

    with TestClient(app) as client:
        token = _bootstrap_and_login(client)
        headers = _auth_headers(token)

        init_upload = client.post(
            "/api/base-models/upload/init",
            headers=headers,
            json={
                "name": "TinyLlama-1.1B",
                "source_kind": "huggingface_ref",
                "source_ref": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                "format": "huggingface",
            },
        )
        base_model = client.post(
            "/api/base-models/upload/complete",
            headers=headers,
            json={"upload_id": init_upload.json()["upload_id"], "storage_uri": "s3://trainplane/base-models/tinyllama"},
        )
        dataset_bundle = client.post(
            "/api/dataset-bundles",
            headers=headers,
            json={
                "project_slug": "orquestra-lab",
                "name": "cancel-bundle",
                "records": [{"instruction": "A", "context": "B", "response": "C"}],
            },
        )
        run = client.post(
            "/api/training-runs",
            headers=headers,
            json={
                "project_slug": "orquestra-lab",
                "name": "cancel-run",
                "base_model_id": base_model.json()["id"],
                "dataset_bundle_id": dataset_bundle.json()["id"],
                "training_profile": {"execution_mode": "qlora", "max_steps": 8},
            },
        )
        run_id = run.json()["id"]

        cancel = client.post(f"/api/training-runs/{run_id}/cancel", headers=headers)
        assert cancel.status_code == 200, cancel.text

        final_payload = cancel.json()
        for _ in range(80):
            current = client.get(f"/api/training-runs/{run_id}", headers=headers)
            final_payload = current.json()
            if final_payload["status"] in {"cancelled", "succeeded", "failed"}:
                break
            time.sleep(0.02)

        assert final_payload["status"] == "cancelled", final_payload
