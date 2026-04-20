from __future__ import annotations

import json
import time
from pathlib import Path
from types import MethodType

from sqlmodel import Session, select

from orquestra_ai.models import ChatSession, WorkflowRun, WorkflowStepRun
from orquestra_ai.workflow_engine import WorkflowCancelled


def _wait_for_final(client, run_id: str, *, timeout: float = 30.0):
    deadline = time.time() + timeout
    final_payload = None
    while time.time() < deadline:
        current = client.get(f"/api/workflows/runs/{run_id}")
        assert current.status_code == 200, current.text
        final_payload = current.json()
        if final_payload["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            return final_payload
        time.sleep(0.25)
    raise AssertionError(f"workflow {run_id} não finalizou a tempo: {final_payload}")


def test_workflow_run_executes_persisted_steps(client):
    session_payload = client.post(
        "/api/chat/sessions",
        json={"title": "workflow", "objective": "Executar workflow local multi-step.", "preset": "assistant"},
    ).json()
    session_id = session_payload["id"]

    workflow = client.post(
        "/api/workflows/runs",
        json={
            "session_id": session_id,
            "workflow_name": "pytest-workflow",
            "summary": "Executar shell seguro e consulta RAG mockada.",
            "steps": [
                {"step_type": "shell_safe", "label": "Git diff", "payload": {"command": "git diff --check"}},
                {
                    "step_type": "rag_query",
                    "label": "RAG mock",
                    "payload": {
                        "question": "Qual é o objetivo atual da sessão?",
                        "session_id": session_id,
                        "mock_llm": True,
                        "memory_enabled": True,
                        "compaction_enabled": True,
                    },
                },
            ],
        },
    )
    assert workflow.status_code == 200, workflow.text
    run_id = workflow.json()["id"]

    final_payload = _wait_for_final(client, run_id)
    assert final_payload["status"] == "succeeded"
    assert len(final_payload["steps"]) == 2
    assert [step["status"] for step in final_payload["steps"]] == ["succeeded", "succeeded"]
    assert final_payload["output_exists"] is True
    assert final_payload["output_preview"]["status"] == "succeeded"
    assert len(final_payload["output_preview"]["steps"]) == 2
    assert "status=succeeded" in final_payload.get("log_tail", "")


def test_workflow_failure_persists_partial_output(client):
    session_payload = client.post(
        "/api/chat/sessions",
        json={"title": "workflow-failure", "objective": "Cobrir falha com saída parcial.", "preset": "assistant"},
    ).json()
    session_id = session_payload["id"]

    workflow = client.post(
        "/api/workflows/runs",
        json={
            "session_id": session_id,
            "workflow_name": "pytest-workflow-failure",
            "summary": "Executar shell seguro e falhar em comando inválido.",
            "steps": [
                {"step_type": "shell_safe", "label": "Git diff", "payload": {"command": "git diff --check"}},
                {"step_type": "shell_safe", "label": "Unsafe command", "payload": {"command": "echo proibido"}},
            ],
        },
    )
    assert workflow.status_code == 200, workflow.text

    final_payload = _wait_for_final(client, workflow.json()["id"])
    assert final_payload["status"] == "failed"
    assert final_payload["output_exists"] is True
    assert final_payload["output_preview"]["status"] == "failed"
    assert final_payload["output_preview"]["failed_step"] == "Unsafe command"
    assert len(final_payload["output_preview"]["steps"]) == 2
    assert final_payload["output_preview"]["steps"][0]["step"] == "Git diff"
    assert "comando não permitido" in final_payload["output_preview"]["error"]


def test_workflow_cancel_persists_cancelled_output(client, monkeypatch):
    session_payload = client.post(
        "/api/chat/sessions",
        json={"title": "workflow-cancel", "objective": "Cobrir cancelamento local.", "preset": "assistant"},
    ).json()
    session_id = session_payload["id"]

    workflow_engine = client.app.state.workflows

    def fake_execute_step(self, session, run, step, cancel_event):
        started = time.time()
        while time.time() - started < 10:
            if cancel_event.is_set():
                raise WorkflowCancelled()
            time.sleep(0.05)
        return {"unexpected": "timeout"}

    monkeypatch.setattr(workflow_engine, "_execute_step", MethodType(fake_execute_step, workflow_engine))

    workflow = client.post(
        "/api/workflows/runs",
        json={
            "session_id": session_id,
            "workflow_name": "pytest-workflow-cancel",
            "summary": "Executar passo longo cancelável.",
            "steps": [
                {"step_type": "shell_safe", "label": "Long step", "payload": {"command": "git diff --check"}},
            ],
        },
    )
    assert workflow.status_code == 200, workflow.text
    run_id = workflow.json()["id"]

    cancel = client.post(f"/api/workflows/runs/{run_id}/cancel")
    assert cancel.status_code == 200, cancel.text

    final_payload = _wait_for_final(client, run_id)
    assert final_payload["status"] == "cancelled"
    assert final_payload["output_exists"] is True
    assert final_payload["output_preview"]["status"] == "cancelled"


def test_workflow_recovery_marks_interrupted_runs(client, tmp_path):
    session_payload = client.post(
        "/api/chat/sessions",
        json={"title": "workflow-recovery", "objective": "Cobrir retomada após restart.", "preset": "assistant"},
    ).json()
    session_id = session_payload["id"]

    lock_path = tmp_path / "stale-workflow.lock"
    lock_path.write_text("locked", encoding="utf-8")
    log_path = tmp_path / "stale-workflow.log"
    output_path = tmp_path / "stale-workflow.json"

    with Session(client.app.state.engine) as session:
        chat_session = session.get(ChatSession, session_id)
        assert chat_session is not None
        run = WorkflowRun(
            session_id=session_id,
            workflow_name="stale-workflow",
            status="running",
            summary="Workflow interrompido durante restart.",
            log_path=str(log_path),
            output_path=str(output_path),
            metadata_json=json.dumps({"owner_pid": 999999, "lock_path": str(lock_path)}, ensure_ascii=False),
        )
        session.add(run)
        session.flush()
        step = WorkflowStepRun(
            run_id=run.id,
            step_index=0,
            step_type="shell_safe",
            label="Stale step",
            status="running",
            input_json=json.dumps({"step_type": "shell_safe"}, ensure_ascii=False),
        )
        session.add(step)
        session.commit()
        run_id = run.id

    client.app.state.workflows.recover_stale_runs()

    with Session(client.app.state.engine) as session:
        recovered = session.get(WorkflowRun, run_id)
        recovered_step = session.exec(select(WorkflowStepRun).where(WorkflowStepRun.run_id == run_id)).first()
        assert recovered is not None
        assert recovered_step is not None
        assert recovered.status == "interrupted"
        assert recovered_step.status == "interrupted"
        metadata = json.loads(recovered.metadata_json or "{}")
        assert metadata["recovered_after_restart"] is True

    payload = client.get(f"/api/workflows/runs/{run_id}")
    assert payload.status_code == 200, payload.text
    assert payload.json()["status"] == "interrupted"
    assert payload.json()["metadata"]["recovered_after_restart"] is True
    assert not Path(lock_path).exists()
