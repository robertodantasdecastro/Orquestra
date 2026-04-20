from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from sqlmodel import Session, select

from .config import TrainPlaneSettings
from .models import TPArtifact, TPTrainingCheckpoint, TPTrainingMetricPoint, TPTrainingRun, utc_now


class TrainPlaneWorker:
    def __init__(self, settings: TrainPlaneSettings, engine) -> None:
        self.settings = settings
        self.engine = engine
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def recover_runs(self) -> None:
        with Session(self.engine) as session:
            rows = session.exec(select(TPTrainingRun).where(TPTrainingRun.status.in_(["queued", "running"]))).all()
            for row in rows:
                row.status = "queued"
                row.updated_at = utc_now()
                session.add(row)
            session.commit()
        for row in rows:
            self.enqueue(row.id)

    def enqueue(self, run_id: str) -> None:
        with self._lock:
            existing = self._threads.get(run_id)
            if existing and existing.is_alive():
                return
            thread = threading.Thread(target=self._execute_run, args=(run_id,), daemon=True)
            self._threads[run_id] = thread
            thread.start()

    def _append_log(self, log_path: Path, line: str) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line.rstrip() + "\n")

    def _execute_run(self, run_id: str) -> None:
        with Session(self.engine) as session:
            run = session.get(TPTrainingRun, run_id)
            if run is None:
                return
            profile = json.loads(run.profile_json or "{}")
            total_steps = int(profile.get("max_steps", 12) or 12)
            run.status = "running"
            run.total_steps = total_steps
            run.started_at = run.started_at or utc_now()
            run.updated_at = utc_now()
            run.logs_path = run.logs_path or str((self.settings.storage_root / "runs" / run.id / "train.log").resolve())
            session.add(run)
            session.commit()
            log_path_value = run.logs_path

        log_path = Path(log_path_value)
        for step in range(1, total_steps + 1):
            with Session(self.engine) as session:
                run = session.get(TPTrainingRun, run_id)
                if run is None:
                    return
                if run.cancel_requested:
                    run.status = "cancelled"
                    run.finished_at = utc_now()
                    run.updated_at = utc_now()
                    run.output_json = json.dumps({"status": "cancelled", "final_step": step - 1}, ensure_ascii=False)
                    session.add(run)
                    session.commit()
                    self._append_log(log_path, f"[trainplane] run={run_id} status=cancelled step={step}")
                    return

                loss = max(0.15, round(2.4 - (step * 0.16), 4))
                eval_loss = round(loss + 0.07, 4)
                metric = TPTrainingMetricPoint(
                    run_id=run.id,
                    step_index=step,
                    epoch=round(step / max(total_steps, 1), 3),
                    loss=loss,
                    eval_loss=eval_loss,
                    learning_rate=round(0.0002 / step, 8),
                    grad_norm=round(1.2 + (step * 0.08), 4),
                    gpu_util=min(98.0, 55.0 + step * 3.0),
                    gpu_mem_gb=min(22.0, 7.5 + step * 0.7),
                    gpu_temp_c=min(84.0, 58.0 + step * 1.6),
                    cpu_percent=min(92.0, 24.0 + step * 2.2),
                    ram_percent=min(89.0, 28.0 + step * 1.9),
                    disk_percent=min(74.0, 31.0 + step * 0.4),
                    network_mbps=round(20.0 + step * 0.9, 2),
                    metadata_json=json.dumps({"mode": profile.get("execution_mode", "simulated")}, ensure_ascii=False),
                )
                session.add(metric)

                run.current_step = step
                run.updated_at = utc_now()
                if step == total_steps:
                    artifact = TPArtifact(
                        run_id=run.id,
                        name=f"{run.name}-adapter",
                        artifact_type="adapter",
                        base_model_name=profile.get("base_model_name", "unknown"),
                        storage_uri=f"{self.settings.public_base_url}/artifacts/{run.id}/adapter",
                        format="adapter-only",
                        benchmark_json=json.dumps(
                            {
                                "correctness": 0.84,
                                "faithfulness": 0.82,
                                "document_relevance": 0.8,
                                "hallucination_rate_proxy": 0.12,
                                "task_success_rate": 0.79,
                            },
                            ensure_ascii=False,
                        ),
                        serving_endpoint_json=json.dumps(
                            {"mode": "simulated", "url": f"{self.settings.public_base_url}/api/artifacts/{run.id}/generate"},
                            ensure_ascii=False,
                        ),
                        metadata_json=json.dumps({"source_run_id": run.id}, ensure_ascii=False),
                    )
                    session.add(artifact)
                    session.flush()
                    run.artifact_id = artifact.id
                    run.status = "succeeded"
                    run.finished_at = utc_now()
                    run.output_json = json.dumps({"status": "succeeded", "artifact_id": artifact.id}, ensure_ascii=False)

                if step in {3, 6, 9, total_steps}:
                    checkpoint = TPTrainingCheckpoint(
                        run_id=run.id,
                        step_index=step,
                        label=f"checkpoint-{step}",
                        storage_uri=f"s3://trainplane/checkpoints/{run.id}/step-{step}",
                        metadata_json=json.dumps({"kind": "qlora"}, ensure_ascii=False),
                    )
                    session.add(checkpoint)

                session.add(run)
                session.commit()

            self._append_log(log_path, f"[trainplane] run={run_id} step={step}/{total_steps} loss={loss:.4f} eval_loss={eval_loss:.4f}")
            time.sleep(self.settings.run_tick_seconds)
