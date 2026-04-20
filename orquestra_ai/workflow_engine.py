from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from .config import OrquestraSettings
from .gateway import OrquestraGateway
from .memory_graph import MemoryGraphService
from .models import MemoryRecord, MemoryReviewCandidate, WorkflowRun, WorkflowStepRun, WorkspaceAsset, utc_now
from .operations import OrquestraOperations
from .rag_memory import RagMemoryService
from .services import (
    LocalRagEngine,
    RagQueryOptions,
    list_gateway_providers,
    workflow_run_to_dict,
)
from .workspace import WorkspaceService

SAFE_SHELL_PREFIXES = (
    "./scripts/",
    "git status",
    "git diff --check",
    "python -m py_compile",
    "npm run build",
    "cargo check",
)


class WorkflowCancelled(Exception):
    pass


class WorkflowEngine:
    def __init__(
        self,
        *,
        settings: OrquestraSettings,
        engine,
        operations: OrquestraOperations,
        memory_graph: MemoryGraphService,
        rag_memory: RagMemoryService,
        workspace_service: WorkspaceService,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.operations = operations
        self.memory_graph = memory_graph
        self.rag_memory = rag_memory
        self.workspace_service = workspace_service
        self.rag_engine = LocalRagEngine(settings)
        self.root = settings.artifacts_root / "workflows"
        self.root.mkdir(parents=True, exist_ok=True)
        self._threads: dict[str, threading.Thread] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self.recover_stale_runs()

    def recover_stale_runs(self) -> None:
        try:
            with Session(self.engine) as session:
                runs = session.exec(select(WorkflowRun).where(WorkflowRun.status.in_(["pending", "running"]))).all()
                changed = False
                for run in runs:
                    metadata = self._safe_json(run.metadata_json, {})
                    owner_pid = int(metadata.get("owner_pid", 0) or 0)
                    lock_value = str(metadata.get("lock_path") or "")
                    lock_path = Path(lock_value) if lock_value else None
                    if owner_pid and self._pid_alive(owner_pid):
                        continue
                    if lock_path and lock_path.exists():
                        try:
                            lock_path.unlink()
                        except OSError:
                            pass
                    run.status = "interrupted"
                    run.finished_at = utc_now()
                    run.metadata_json = json.dumps(metadata | {"recovered_after_restart": True}, ensure_ascii=False)
                    session.add(run)
                    steps = session.exec(select(WorkflowStepRun).where(WorkflowStepRun.run_id == run.id)).all()
                    for step in steps:
                        if step.status == "running":
                            step.status = "interrupted"
                            step.finished_at = utc_now()
                            session.add(step)
                    changed = True
                if changed:
                    session.commit()
        except OperationalError:
            return

    def list_runs(self, session: Session, *, limit: int = 20) -> list[dict[str, Any]]:
        runs = session.exec(select(WorkflowRun).order_by(WorkflowRun.started_at.desc()).limit(limit)).all()
        return [self._build_run_payload(session, run) for run in runs]

    def get_run(self, session: Session, run_id: str) -> dict[str, Any]:
        run = session.get(WorkflowRun, run_id)
        if run is None:
            raise KeyError(run_id)
        return self._build_run_payload(session, run)

    def create_run(
        self,
        *,
        session_id: str | None,
        task_id: str | None,
        workflow_name: str,
        summary: str,
        steps: list[dict[str, Any]],
    ) -> str:
        with Session(self.engine) as session:
            run_dir = self.root / utc_now().strftime("%Y%m%d") / workflow_name.replace("/", "-")
            run_dir.mkdir(parents=True, exist_ok=True)
            unique_suffix = str(int(time.time()))
            log_path = run_dir / f"{workflow_name.replace('/', '-')}-{unique_suffix}.log"
            output_path = run_dir / f"{workflow_name.replace('/', '-')}-{unique_suffix}.json"
            lock_path = run_dir / f"{workflow_name.replace('/', '-')}-{unique_suffix}.lock"
            lock_path.write_text(json.dumps({"owner_pid": os.getpid(), "created_at": utc_now().isoformat()}), encoding="utf-8")
            run = WorkflowRun(
                session_id=session_id,
                task_id=task_id,
                workflow_name=workflow_name,
                status="pending",
                summary=summary,
                log_path=str(log_path),
                output_path=str(output_path),
                metadata_json=json.dumps({"step_count": len(steps), "owner_pid": os.getpid(), "lock_path": str(lock_path)}, ensure_ascii=False),
            )
            session.add(run)
            session.flush()
            for index, step in enumerate(steps):
                session.add(
                    WorkflowStepRun(
                        run_id=run.id,
                        step_index=index,
                        step_type=str(step.get("step_type") or ""),
                        label=str(step.get("label") or step.get("step_type") or f"step-{index}"),
                        status="pending",
                        input_json=json.dumps(step, ensure_ascii=False),
                    )
                )
            session.commit()
            run_id = run.id

        cancel_event = threading.Event()
        self._cancel_events[run_id] = cancel_event
        thread = threading.Thread(target=self._run_workflow, args=(run_id,), daemon=True)
        self._threads[run_id] = thread
        thread.start()
        return run_id

    def cancel_run(self, run_id: str) -> None:
        with Session(self.engine) as session:
            run = session.get(WorkflowRun, run_id)
            if run is None:
                raise KeyError(run_id)
            run.cancel_requested = True
            run.metadata_json = json.dumps(
                self._safe_json(run.metadata_json, {}) | {"cancel_requested_at": utc_now().isoformat()},
                ensure_ascii=False,
            )
            session.add(run)
            session.commit()
        event = self._cancel_events.get(run_id)
        if event is not None:
            event.set()

    def _run_workflow(self, run_id: str) -> None:
        cancel_event = self._cancel_events.setdefault(run_id, threading.Event())
        with Session(self.engine) as session:
            run = session.get(WorkflowRun, run_id)
            if run is None:
                return
            self._append_run_log(Path(run.log_path), f"[workflow] started_at={utc_now().isoformat()}")
            run.status = "running"
            session.add(run)
            session.commit()

        outputs: list[dict[str, Any]] = []
        try:
            with Session(self.engine) as session:
                run = session.get(WorkflowRun, run_id)
                if run is None:
                    return
                steps = session.exec(select(WorkflowStepRun).where(WorkflowStepRun.run_id == run_id).order_by(WorkflowStepRun.step_index)).all()
                for index, step in enumerate(steps):
                    session.refresh(run)
                    if cancel_event.is_set() or run.cancel_requested:
                        raise WorkflowCancelled()
                    step.status = "running"
                    step.started_at = utc_now()
                    session.add(step)
                    session.commit()

                    try:
                        self._append_run_log(Path(run.log_path), f"[workflow] step={step.step_index} label={step.label} status=running")
                        output = self._execute_step(session, run, step, cancel_event)
                    except WorkflowCancelled:
                        self._append_run_log(Path(run.log_path), f"[workflow] step={step.step_index} label={step.label} status=cancelled")
                        step.status = "cancelled"
                        step.finished_at = utc_now()
                        session.add(step)
                        run.status = "cancelled"
                        run.finished_at = utc_now()
                        session.add(run)
                        session.commit()
                        return
                    except Exception as exc:
                        self._append_run_log(Path(run.log_path), f"[workflow] step={step.step_index} label={step.label} status=failed error={exc}")
                        step.status = "failed"
                        step.output_json = json.dumps({"error": str(exc)}, ensure_ascii=False)
                        step.finished_at = utc_now()
                        session.add(step)
                        run.status = "failed"
                        run.finished_at = utc_now()
                        run.metadata_json = json.dumps(
                            self._safe_json(run.metadata_json, {}) | {"error": str(exc), "failed_step": step.label},
                            ensure_ascii=False,
                        )
                        session.add(run)
                        session.commit()
                        return

                    outputs.append({"step": step.label, "output": output})
                    self._append_run_log(Path(run.log_path), f"[workflow] step={step.step_index} label={step.label} status=succeeded")
                    step.status = "succeeded"
                    step.output_json = json.dumps(output, ensure_ascii=False)
                    step.finished_at = utc_now()
                    session.add(step)
                    run.progress = round((index + 1) / max(len(steps), 1), 4)
                    run.metadata_json = json.dumps(
                        self._safe_json(run.metadata_json, {}) | {"completed_steps": index + 1},
                        ensure_ascii=False,
                    )
                    session.add(run)
                    session.commit()

                Path(run.output_path).write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
                self._append_run_log(Path(run.log_path), "[workflow] status=succeeded")
                run.status = "succeeded"
                run.progress = 1.0
                run.finished_at = utc_now()
                session.add(run)
                session.commit()
        finally:
            with Session(self.engine) as session:
                run = session.get(WorkflowRun, run_id)
                metadata = self._safe_json(run.metadata_json, {}) if run is not None else {}
                lock_value = str(metadata.get("lock_path") or "")
                lock_path = Path(lock_value) if lock_value else None
                if lock_path and lock_path.exists():
                    try:
                        lock_path.unlink()
                    except OSError:
                        pass
            self._threads.pop(run_id, None)
            self._cancel_events.pop(run_id, None)

    def _execute_step(
        self,
        session: Session,
        run: WorkflowRun,
        step: WorkflowStepRun,
        cancel_event: threading.Event,
    ) -> dict[str, Any]:
        payload = self._safe_json(step.input_json, {})
        step_type = step.step_type
        if step_type == "ops_action":
            action_id = str(payload.get("action_id") or "")
            if not action_id:
                raise ValueError("step ops_action sem action_id")
            step_log = Path(run.log_path).with_name(f"{Path(run.log_path).stem}-step-{step.step_index:02d}.log")
            exit_code = self.operations.run_action_sync(action_id, log_path=step_log, cancel_event=cancel_event)
            return {"action_id": action_id, "exit_code": exit_code, "log_path": str(step_log)}

        if step_type == "rag_query":
            result = self.rag_engine.query(
                session,
                RagQueryOptions(
                    question=str(payload.get("question") or ""),
                    session_id=payload.get("session_id"),
                    collection_name=payload.get("collection_name"),
                    provider_id=payload.get("provider_id"),
                    model_name=payload.get("model_name"),
                    expected_output=payload.get("expected_output"),
                    task_type=str(payload.get("task_type") or "workflow"),
                    remember=bool(payload.get("remember", False)),
                    mock_llm=bool(payload.get("mock_llm", False)),
                    memory_enabled=bool(payload.get("memory_enabled", True)),
                    memory_scopes=payload.get("memory_scopes") or None,
                    include_workspace=bool(payload.get("include_workspace", True)),
                    include_sources=bool(payload.get("include_sources", True)),
                    max_context_chars=int(payload.get("max_context_chars", 9000)),
                    compaction_enabled=bool(payload.get("compaction_enabled", True)),
                    planner_enabled=bool(payload.get("planner_enabled", True)),
                    task_context_enabled=bool(payload.get("task_context_enabled", True)),
                    memory_selector_mode=str(payload.get("memory_selector_mode") or "hybrid"),
                    context_budget=payload.get("context_budget"),
                ),
                project_id=payload.get("project_id"),
            )
            session.commit()
            return {
                "answer": result.get("answer"),
                "provider_id": result.get("provider_id"),
                "model_name": result.get("model_name"),
                "citations": result.get("citations", []),
            }

        if step_type == "workspace_query":
            gateway = OrquestraGateway(list_gateway_providers(session), mock=bool(payload.get("mock_response", False)))
            result = self.workspace_service.query_workspace(
                session,
                gateway,
                scan_id=str(payload.get("scan_id") or ""),
                prompt=str(payload.get("prompt") or ""),
                provider_id=payload.get("provider_id") or self.settings.default_provider_id,
                model_name=payload.get("model_name") or self.settings.local_chat_model,
                force_extract=bool(payload.get("force_extract", False)),
            )
            session.commit()
            return result

        if step_type == "workspace_extract":
            asset_id = str(payload.get("asset_id") or "")
            asset = session.get(WorkspaceAsset, asset_id)
            if asset is None:
                raise ValueError(f"asset não encontrado: {asset_id}")
            result = self.workspace_service.extract_asset(
                session,
                asset,
                force=bool(payload.get("force", False)),
                prompt_hint=str(payload.get("prompt_hint") or ""),
            )
            session.commit()
            return result

        if step_type == "memory_review_batch":
            decision = str(payload.get("decision") or "approve")
            candidate_ids = [str(item) for item in payload.get("candidate_ids", [])]
            results: list[dict[str, Any]] = []
            for candidate_id in candidate_ids:
                candidate = session.get(MemoryReviewCandidate, candidate_id)
                if candidate is None or candidate.status != "pending":
                    continue
                metadata = self._safe_json(candidate.metadata_json, {})
                if decision == "reject":
                    candidate.status = "rejected"
                    candidate.reviewed_at = utc_now()
                    candidate.metadata_json = json.dumps(metadata | {"workflow_reviewed_at": utc_now().isoformat()}, ensure_ascii=False)
                    session.add(candidate)
                    results.append({"candidate_id": candidate.id, "status": candidate.status})
                    continue

                record = MemoryRecord(
                    project_id=candidate.project_id,
                    session_id=candidate.session_id,
                    scope=candidate.scope,
                    memory_kind=candidate.memory_kind,
                    source=f"workflow_memory_candidate:{candidate.id}",
                    content=candidate.content,
                    confidence=candidate.confidence,
                    approved_for_training=bool(payload.get("create_training_candidate", False)),
                    metadata_json=json.dumps(metadata | {"workflow_reviewed": True}, ensure_ascii=False),
                )
                session.add(record)
                session.flush()
                self.memory_graph.project_memory_record(session, record, title=candidate.title, metadata=self._safe_json(record.metadata_json, {}))
                self.rag_memory.upsert_memory(
                    record,
                    title=candidate.title,
                    preset=str(metadata.get("preset", "")),
                    source_kind="memory_candidate",
                    source_ref=candidate.id,
                    approved=True,
                )
                candidate.status = "approved"
                candidate.reviewed_at = utc_now()
                session.add(candidate)
                results.append({"candidate_id": candidate.id, "status": candidate.status, "record_id": record.id})
            session.commit()
            return {"decision": decision, "results": results}

        if step_type == "shell_safe":
            command = str(payload.get("command") or "")
            if not self._is_safe_shell(command):
                raise ValueError(f"comando não permitido no shell_safe: {command}")
            step_log = Path(run.log_path).with_name(f"{Path(run.log_path).stem}-shell-{step.step_index:02d}.log")
            exit_code = self._run_shell(command, log_path=step_log, cancel_event=cancel_event)
            return {"command": command, "exit_code": exit_code, "log_path": str(step_log)}

        raise ValueError(f"step_type não suportado: {step_type}")

    def _run_shell(self, command: str, *, log_path: Path, cancel_event: threading.Event) -> int:
        env = os.environ.copy()
        env.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
        with log_path.open("w", encoding="utf-8") as handle:
            handle.write(f"[workflow] command={command}\n")
            handle.write(f"[workflow] started_at={utc_now().isoformat()}\n\n")
            handle.flush()
            process = subprocess.Popen(
                ["/bin/bash", "-lc", command],
                cwd=self.settings.workspace_root,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            while True:
                if cancel_event.is_set():
                    process.terminate()
                    try:
                        code = process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        code = process.wait()
                    handle.write("\n[workflow] cancelled=true\n")
                    handle.write(f"[workflow] exit_code={code}\n")
                    raise WorkflowCancelled()
                code = process.poll()
                if code is not None:
                    handle.write(f"\n[workflow] exit_code={code}\n")
                    return code
                time.sleep(0.2)

    def _build_run_payload(self, session: Session, run: WorkflowRun) -> dict[str, Any]:
        steps = session.exec(select(WorkflowStepRun).where(WorkflowStepRun.run_id == run.id).order_by(WorkflowStepRun.step_index)).all()
        payload = workflow_run_to_dict(run, steps=steps)
        log_path = Path(run.log_path)
        if log_path.exists():
            payload["log_tail"] = log_path.read_text(encoding="utf-8", errors="ignore")[-6000:]
        else:
            payload["log_tail"] = ""
        return payload

    @staticmethod
    def _is_safe_shell(command: str) -> bool:
        normalized = command.strip()
        return any(normalized.startswith(prefix) for prefix in SAFE_SHELL_PREFIXES)

    @staticmethod
    def _safe_json(raw: str | None, fallback: Any) -> Any:
        try:
            return json.loads(raw or "")
        except Exception:
            return fallback

    @staticmethod
    def _append_run_log(path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line.rstrip() + "\n")

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
