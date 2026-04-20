from __future__ import annotations

import time


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

    final_payload = None
    for _ in range(120):
        current = client.get(f"/api/workflows/runs/{run_id}")
        assert current.status_code == 200, current.text
        final_payload = current.json()
        if final_payload["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            break
        time.sleep(0.25)

    assert final_payload is not None
    assert final_payload["status"] == "succeeded"
    assert len(final_payload["steps"]) == 2
    assert [step["status"] for step in final_payload["steps"]] == ["succeeded", "succeeded"]
    assert "status=succeeded" in final_payload.get("log_tail", "")
