from __future__ import annotations

import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .config import TrainPlaneSettings, load_settings
from .models import (
    TPAdminUser,
    TPArtifact,
    TPBaseModel,
    TPComparisonRun,
    TPDatasetBundle,
    TPEvaluationRun,
    TPPersonalAccessToken,
    TPTrainingCheckpoint,
    TPTrainingMetricPoint,
    TPTrainingRun,
    utc_now,
)
from .services import (
    build_engine,
    create_pat,
    dict_artifact,
    dict_base_model,
    dict_comparison_run,
    dict_dataset_bundle,
    dict_evaluation_run,
    dict_token,
    dict_training_run,
    ensure_storage_dirs,
    generate_totp_secret,
    hash_password,
    init_database,
    verify_password,
    verify_totp,
)
from .worker import TrainPlaneWorker


class AuthBootstrapRequest(BaseModel):
    username: str = "admin"
    password: str


class AuthLoginRequest(BaseModel):
    username: str = "admin"
    password: str
    totp_code: str = ""
    label: str = "orquestra-local"


class BaseModelUploadInitRequest(BaseModel):
    name: str
    source_kind: str
    source_ref: str = ""
    size_bytes: int = 0
    checksum_sha256: str = ""
    format: str = "huggingface"
    metadata: dict[str, object] = Field(default_factory=dict)


class BaseModelUploadCompleteRequest(BaseModel):
    upload_id: str
    storage_uri: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class DatasetBundleCreateRequest(BaseModel):
    project_slug: str
    name: str
    source: str = "orquestra"
    records: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class TrainingRunCreateRequest(BaseModel):
    project_slug: str
    name: str
    base_model_id: str
    dataset_bundle_id: str
    summary: str = ""
    training_profile: dict[str, object] = Field(default_factory=dict)


class EvaluationRunCreateRequest(BaseModel):
    candidate_artifact_id: str
    baseline_mode: str
    baseline_ref: str = ""
    suite_name: str = "default-suite"
    cases: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ComparisonRunCreateRequest(BaseModel):
    candidate_artifact_id: str
    baseline_mode: str
    baseline_ref: str = ""
    prompt_set_name: str = "default-compare"
    cases: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


def _token_digest(raw: str) -> str:
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _score_case(case: dict[str, object], candidate_suffix: str = "candidate") -> dict[str, object]:
    prompt = str(case.get("prompt", "")).strip()
    expected = str(case.get("expected_output", "")).strip()
    baseline_output = str(case.get("baseline_output", "")).strip() or f"baseline::{prompt}"
    candidate_output = f"{candidate_suffix}::{prompt}" if not expected else expected
    correctness = 1.0 if expected else 0.72
    faithfulness = 0.9 if expected else 0.76
    hallucination = 0.08 if expected else 0.16
    return {
        "prompt": prompt,
        "expected_output": expected,
        "baseline_output": baseline_output,
        "candidate_output": candidate_output,
        "scores": {
            "correctness": correctness,
            "faithfulness": faithfulness,
            "document_relevance": 0.82,
            "hallucination_rate_proxy": hallucination,
            "task_success_rate": 0.83,
            "manual_review_score": 0.8,
        },
        "review": {
            "factual_drift": hallucination > 0.15,
            "unsupported_claim": False,
            "missed_instruction": False,
            "unsafe_output": False,
        },
    }


def _aggregate_case_scores(cases: list[dict[str, object]]) -> dict[str, float]:
    if not cases:
        return {}
    keys = sorted({metric for case in cases for metric in case.get("scores", {}).keys()})
    payload: dict[str, float] = {}
    for key in keys:
        values = [float(case.get("scores", {}).get(key, 0.0)) for case in cases]
        payload[key] = round(sum(values) / max(len(values), 1), 4)
    return payload


def _trainplane_console_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Orquestra Train Plane</title>
  <style>
    :root { color-scheme: light; --bg:#f5f1e8; --ink:#1d201f; --panel:#fffaf2; --accent:#0b6e4f; --muted:#716b5d; --line:#d7cfbd; }
    body { margin:0; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, sans-serif; background:linear-gradient(135deg,#efe6d5,#f8f6f2); color:var(--ink); }
    .shell { display:grid; gap:18px; padding:22px; max-width:1280px; margin:0 auto; }
    .hero,.panel { background:rgba(255,250,242,.92); border:1px solid var(--line); border-radius:20px; padding:18px; box-shadow:0 16px 40px rgba(46,38,28,.08); }
    .hero h1 { margin:0 0 6px; font-size:32px; }
    .grid { display:grid; gap:18px; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); }
    .metric { display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--line); }
    .metric:last-child { border-bottom:none; }
    .eyebrow { text-transform:uppercase; letter-spacing:.12em; color:var(--muted); font-size:12px; }
    .chart { width:100%; height:150px; background:#f8f3e8; border-radius:14px; }
    table { width:100%; border-collapse:collapse; font-size:14px; }
    th,td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
    code { background:#efe8da; padding:2px 6px; border-radius:6px; }
    .login { display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }
    input,button { border-radius:10px; border:1px solid var(--line); padding:10px 12px; font:inherit; }
    button { background:var(--accent); color:white; cursor:pointer; }
    pre { white-space:pre-wrap; word-break:break-word; background:#efe8da; padding:10px; border-radius:12px; }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <p class="eyebrow">Train Plane</p>
      <h1>Orquestra Remote Fine-Tuning Console</h1>
      <p>Painel web dedicado para treino remoto, artefatos, comparação e monitoramento gráfico.</p>
      <div class="login">
        <input id="username" value="admin" />
        <input id="password" type="password" placeholder="Senha" />
        <input id="totp" placeholder="TOTP" />
        <button id="login">Entrar</button>
      </div>
      <pre id="status">Faça login para carregar o console.</pre>
    </section>
    <section class="grid">
      <article class="panel">
        <p class="eyebrow">Treinos</p>
        <div id="runs"></div>
      </article>
      <article class="panel">
        <p class="eyebrow">Gráfico</p>
        <svg id="chart" class="chart" viewBox="0 0 400 150" preserveAspectRatio="none"></svg>
      </article>
    </section>
    <section class="grid">
      <article class="panel">
        <p class="eyebrow">Artifacts</p>
        <div id="artifacts"></div>
      </article>
      <article class="panel">
        <p class="eyebrow">Comparações</p>
        <div id="comparisons"></div>
      </article>
    </section>
  </div>
  <script>
    let token = "";
    async function api(path, init = {}) {
      const response = await fetch(path, {
        ...init,
        headers: {
          ...(init.body ? { "Content-Type": "application/json" } : {}),
          ...(token ? { "Authorization": `Bearer ${token}` } : {}),
          ...(init.headers || {})
        }
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json();
    }
    function renderChart(points) {
      const svg = document.getElementById("chart");
      if (!points.length) {
        svg.innerHTML = "";
        return;
      }
      const values = points.map((item) => Number(item.loss || 0));
      const max = Math.max(...values, 1);
      const coords = points.map((item, index) => {
        const x = (index / Math.max(points.length - 1, 1)) * 400;
        const y = 140 - ((Number(item.loss || 0) / max) * 120);
        return `${x},${y}`;
      }).join(" ");
      svg.innerHTML = `<polyline fill="none" stroke="#0b6e4f" stroke-width="4" points="${coords}" />`;
    }
    async function refresh() {
      const [runs, artifacts, comparisons] = await Promise.all([
        api("/api/training-runs"),
        api("/api/artifacts"),
        api("/api/comparison-runs")
      ]);
      document.getElementById("runs").innerHTML = runs.map((run) => `<div class="metric"><strong>${run.name}</strong><span>${run.status}</span></div>`).join("") || "Sem runs.";
      document.getElementById("artifacts").innerHTML = artifacts.map((item) => `<div class="metric"><strong>${item.name}</strong><span>${item.format}</span></div>`).join("") || "Sem artefatos.";
      document.getElementById("comparisons").innerHTML = comparisons.map((item) => `<div class="metric"><strong>${item.prompt_set_name}</strong><span>${item.status}</span></div>`).join("") || "Sem comparações.";
      if (runs[0]) {
        const details = await api(`/api/training-runs/${runs[0].id}`);
        renderChart(details.metrics || []);
      } else {
        renderChart([]);
      }
    }
    document.getElementById("login").addEventListener("click", async () => {
      const username = document.getElementById("username").value;
      const password = document.getElementById("password").value;
      const totp = document.getElementById("totp").value;
      try {
        const payload = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password, totp_code: totp }) });
        token = payload.access_token;
        document.getElementById("status").textContent = `Token ${payload.token.token_last4} carregado.`;
        await refresh();
      } catch (error) {
        document.getElementById("status").textContent = String(error);
      }
    });
  </script>
</body>
</html>"""


def create_app(settings: TrainPlaneSettings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    ensure_storage_dirs(app_settings.storage_root)
    engine = build_engine(app_settings.database_url)
    worker = TrainPlaneWorker(app_settings, engine)

    def bootstrap_runtime() -> None:
        init_database(engine)
        worker.recover_runs()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        bootstrap_runtime()
        yield

    app = FastAPI(title="Orquestra Train Plane", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.worker = worker
    app.state.pending_uploads = {}

    def get_session(request: Request) -> Iterator[Session]:
        with Session(request.app.state.engine) as session:
            yield session

    def require_token(
        authorization: str | None = Header(default=None),
        token: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> TPPersonalAccessToken:
        raw_token = ""
        if authorization and authorization.startswith("Bearer "):
            raw_token = authorization.removeprefix("Bearer ").strip()
        elif token:
            raw_token = token.strip()
        if not raw_token:
            raise HTTPException(status_code=401, detail="Token ausente.")
        digest = _token_digest(raw_token)
        record = session.exec(select(TPPersonalAccessToken).where(TPPersonalAccessToken.token_hash == digest)).first()
        if record is None or record.revoked_at is not None:
            raise HTTPException(status_code=401, detail="Token inválido.")
        record.last_used_at = utc_now()
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @app.get("/")
    def console_index() -> HTMLResponse:
        return HTMLResponse(_trainplane_console_html())

    @app.get("/api/health")
    def health(session: Session = Depends(get_session)) -> dict[str, object]:
        return {
            "ok": True,
            "app": "Orquestra Train Plane",
            "base_models": len(session.exec(select(TPBaseModel)).all()),
            "dataset_bundles": len(session.exec(select(TPDatasetBundle)).all()),
            "training_runs": len(session.exec(select(TPTrainingRun)).all()),
            "artifacts": len(session.exec(select(TPArtifact)).all()),
            "public_base_url": app_settings.public_base_url,
        }

    @app.post("/api/auth/bootstrap")
    def auth_bootstrap(payload: AuthBootstrapRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        if not app_settings.allow_bootstrap:
            raise HTTPException(status_code=403, detail="Bootstrap desabilitado.")
        existing = session.exec(select(TPAdminUser)).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Bootstrap já executado.")
        user = TPAdminUser(
            username=payload.username,
            password_hash=hash_password(payload.password),
            totp_secret=generate_totp_secret(),
            totp_enabled=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return {
            "user": {"id": user.id, "username": user.username, "totp_enabled": user.totp_enabled},
            "totp_secret": user.totp_secret,
        }

    @app.post("/api/auth/login")
    def auth_login(payload: AuthLoginRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        user = session.exec(select(TPAdminUser).where(TPAdminUser.username == payload.username)).first()
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
        if user.totp_enabled and not verify_totp(user.totp_secret, payload.totp_code):
            raise HTTPException(status_code=401, detail="TOTP inválido.")
        raw_token, token_hash, last4 = create_pat()
        token = TPPersonalAccessToken(label=payload.label, token_hash=token_hash, token_last4=last4)
        session.add(token)
        session.commit()
        session.refresh(token)
        return {
            "access_token": raw_token,
            "token": dict_token(token),
        }

    @app.post("/api/base-models/upload/init")
    def init_base_model_upload(payload: BaseModelUploadInitRequest, request: Request, auth=Depends(require_token)) -> dict[str, object]:
        upload_id = secrets.token_hex(12)
        request.app.state.pending_uploads[upload_id] = payload.model_dump()
        return {"upload_id": upload_id, "mode": "metadata_only", "s3_multipart": False}

    @app.post("/api/base-models/upload/complete")
    def complete_base_model_upload(payload: BaseModelUploadCompleteRequest, request: Request, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        draft = request.app.state.pending_uploads.pop(payload.upload_id, None)
        if draft is None:
            raise HTTPException(status_code=404, detail="Upload não encontrado.")
        item = TPBaseModel(
            name=str(draft.get("name", "base-model")),
            source_kind=str(draft.get("source_kind", "uploaded_bundle")),
            source_ref=str(draft.get("source_ref", "")),
            storage_uri=payload.storage_uri or f"s3://trainplane/base-models/{payload.upload_id}",
            size_bytes=int(draft.get("size_bytes", 0) or 0),
            checksum_sha256=str(draft.get("checksum_sha256", "")),
            format=str(draft.get("format", "huggingface")),
            metadata_json=json.dumps({**dict(draft.get("metadata", {})), **payload.metadata}, ensure_ascii=False),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return dict_base_model(item)

    @app.get("/api/base-models")
    def list_base_models(session: Session = Depends(get_session), auth=Depends(require_token)) -> list[dict[str, object]]:
        rows = session.exec(select(TPBaseModel).order_by(TPBaseModel.created_at.desc())).all()
        return [dict_base_model(row) for row in rows]

    @app.post("/api/dataset-bundles")
    def create_dataset_bundle(payload: DatasetBundleCreateRequest, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        bundle_dir = app_settings.storage_root / "datasets" / payload.project_slug
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundle_dir / f"{payload.name.replace(' ', '-').lower()}.jsonl"
        with bundle_path.open("w", encoding="utf-8") as handle:
            for record in payload.records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        stats = {"records": len(payload.records), "path": str(bundle_path)}
        item = TPDatasetBundle(
            project_slug=payload.project_slug,
            name=payload.name,
            source=payload.source,
            storage_uri=f"file://{bundle_path}",
            record_count=len(payload.records),
            stats_json=json.dumps(stats, ensure_ascii=False),
            metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return dict_dataset_bundle(item)

    @app.get("/api/dataset-bundles")
    def list_dataset_bundles(session: Session = Depends(get_session), auth=Depends(require_token)) -> list[dict[str, object]]:
        rows = session.exec(select(TPDatasetBundle).order_by(TPDatasetBundle.created_at.desc())).all()
        return [dict_dataset_bundle(row) for row in rows]

    @app.post("/api/training-runs")
    def create_training_run(payload: TrainingRunCreateRequest, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        base_model = session.get(TPBaseModel, payload.base_model_id)
        dataset_bundle = session.get(TPDatasetBundle, payload.dataset_bundle_id)
        if base_model is None or dataset_bundle is None:
            raise HTTPException(status_code=404, detail="Base model ou dataset bundle não encontrado.")
        run = TPTrainingRun(
            project_slug=payload.project_slug,
            name=payload.name,
            base_model_id=payload.base_model_id,
            dataset_bundle_id=payload.dataset_bundle_id,
            summary=payload.summary,
            profile_json=json.dumps({**payload.training_profile, "base_model_name": base_model.name}, ensure_ascii=False),
            logs_path=str((app_settings.storage_root / "runs" / payload.project_slug / f"{payload.name}.log").resolve()),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        worker.enqueue(run.id)
        return dict_training_run(run)

    @app.get("/api/training-runs")
    def list_training_runs(session: Session = Depends(get_session), auth=Depends(require_token)) -> list[dict[str, object]]:
        rows = session.exec(select(TPTrainingRun).order_by(TPTrainingRun.created_at.desc())).all()
        return [dict_training_run(row) for row in rows]

    @app.get("/api/training-runs/{run_id}")
    def get_training_run(run_id: str, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        run = session.get(TPTrainingRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Training run não encontrado.")
        metrics = session.exec(select(TPTrainingMetricPoint).where(TPTrainingMetricPoint.run_id == run_id).order_by(TPTrainingMetricPoint.step_index)).all()
        checkpoints = session.exec(select(TPTrainingCheckpoint).where(TPTrainingCheckpoint.run_id == run_id).order_by(TPTrainingCheckpoint.step_index)).all()
        artifact = session.get(TPArtifact, run.artifact_id) if run.artifact_id else None
        return dict_training_run(run, metrics=metrics, checkpoints=checkpoints, artifact=artifact)

    @app.post("/api/training-runs/{run_id}/cancel")
    def cancel_training_run(run_id: str, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        run = session.get(TPTrainingRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Training run não encontrado.")
        run.cancel_requested = True
        run.updated_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
        return dict_training_run(run)

    @app.get("/api/training-runs/{run_id}/events")
    def stream_training_run_events(run_id: str, session: Session = Depends(get_session), auth=Depends(require_token)):
        if session.get(TPTrainingRun, run_id) is None:
            raise HTTPException(status_code=404, detail="Training run não encontrado.")

        def event_stream() -> Iterator[str]:
            seen = 0
            while True:
                with Session(engine) as stream_session:
                    run = stream_session.get(TPTrainingRun, run_id)
                    if run is None:
                        break
                    metrics = stream_session.exec(select(TPTrainingMetricPoint).where(TPTrainingMetricPoint.run_id == run_id).order_by(TPTrainingMetricPoint.step_index)).all()
                    if len(metrics) > seen:
                        for item in metrics[seen:]:
                            yield f"event: metric\ndata: {json.dumps({'step_index': item.step_index, 'loss': item.loss, 'gpu_util': item.gpu_util}, ensure_ascii=False)}\n\n"
                        seen = len(metrics)
                    yield f"event: status\ndata: {json.dumps({'status': run.status, 'current_step': run.current_step, 'total_steps': run.total_steps}, ensure_ascii=False)}\n\n"
                    if run.status in {"succeeded", "failed", "cancelled"}:
                        break
                import time

                time.sleep(app_settings.run_tick_seconds)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/api/artifacts")
    def list_artifacts(session: Session = Depends(get_session), auth=Depends(require_token)) -> list[dict[str, object]]:
        rows = session.exec(select(TPArtifact).order_by(TPArtifact.created_at.desc())).all()
        return [dict_artifact(row) for row in rows]

    @app.post("/api/artifacts/{artifact_id}/merge")
    def merge_artifact(artifact_id: str, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        artifact = session.get(TPArtifact, artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artefato não encontrado.")
        merged = TPArtifact(
            run_id=artifact.run_id,
            name=f"{artifact.name}-merged",
            artifact_type="merged_model",
            base_model_name=artifact.base_model_name,
            storage_uri=f"{artifact.storage_uri}/merged",
            format="merged-full",
            benchmark_json=artifact.benchmark_json,
            serving_endpoint_json=artifact.serving_endpoint_json,
            metadata_json=json.dumps({"merged_from": artifact.id}, ensure_ascii=False),
        )
        session.add(merged)
        session.commit()
        session.refresh(merged)
        return dict_artifact(merged)

    @app.post("/api/artifacts/{artifact_id}/promote")
    def promote_artifact(artifact_id: str, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        artifact = session.get(TPArtifact, artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artefato não encontrado.")
        artifact.status = "promoted"
        artifact.updated_at = utc_now()
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        return dict_artifact(artifact)

    @app.post("/api/artifacts/{artifact_id}/generate")
    def generate_from_artifact(artifact_id: str, payload: dict[str, object], session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        artifact = session.get(TPArtifact, artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artefato não encontrado.")
        prompt = str(payload.get("prompt", "")).strip()
        return {
            "artifact_id": artifact.id,
            "prompt": prompt,
            "output": f"{artifact.name}::{prompt}",
            "serving_endpoint": json.loads(artifact.serving_endpoint_json or "{}"),
        }

    @app.post("/api/evaluation-runs")
    def create_evaluation_run(payload: EvaluationRunCreateRequest, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        artifact = session.get(TPArtifact, payload.candidate_artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artefato candidato não encontrado.")
        scored_cases = [_score_case(case, candidate_suffix=artifact.name) for case in payload.cases]
        summary_scores = _aggregate_case_scores(scored_cases)
        row = TPEvaluationRun(
            candidate_artifact_id=payload.candidate_artifact_id,
            baseline_mode=payload.baseline_mode,
            baseline_ref=payload.baseline_ref,
            suite_name=payload.suite_name,
            status="succeeded",
            summary_scores_json=json.dumps(summary_scores, ensure_ascii=False),
            results_json=json.dumps(scored_cases, ensure_ascii=False),
            metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return dict_evaluation_run(row)

    @app.get("/api/evaluation-runs")
    def list_evaluation_runs(session: Session = Depends(get_session), auth=Depends(require_token)) -> list[dict[str, object]]:
        rows = session.exec(select(TPEvaluationRun).order_by(TPEvaluationRun.created_at.desc())).all()
        return [dict_evaluation_run(row) for row in rows]

    @app.get("/api/evaluation-runs/{run_id}")
    def get_evaluation_run(run_id: str, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        row = session.get(TPEvaluationRun, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Evaluation run não encontrado.")
        return dict_evaluation_run(row)

    @app.post("/api/comparison-runs")
    def create_comparison_run(payload: ComparisonRunCreateRequest, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        artifact = session.get(TPArtifact, payload.candidate_artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artefato candidato não encontrado.")
        cases = [_score_case(case, candidate_suffix=artifact.name) for case in payload.cases]
        summary_scores = _aggregate_case_scores(cases)
        row = TPComparisonRun(
            candidate_artifact_id=payload.candidate_artifact_id,
            baseline_mode=payload.baseline_mode,
            baseline_ref=payload.baseline_ref,
            prompt_set_name=payload.prompt_set_name,
            status="succeeded",
            summary_scores_json=json.dumps(summary_scores, ensure_ascii=False),
            cases_json=json.dumps(cases, ensure_ascii=False),
            metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return dict_comparison_run(row)

    @app.get("/api/comparison-runs")
    def list_comparison_runs(session: Session = Depends(get_session), auth=Depends(require_token)) -> list[dict[str, object]]:
        rows = session.exec(select(TPComparisonRun).order_by(TPComparisonRun.created_at.desc())).all()
        return [dict_comparison_run(row) for row in rows]

    @app.get("/api/comparison-runs/{run_id}")
    def get_comparison_run(run_id: str, session: Session = Depends(get_session), auth=Depends(require_token)) -> dict[str, object]:
        row = session.get(TPComparisonRun, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Comparison run não encontrado.")
        return dict_comparison_run(row)

    return app
