from __future__ import annotations

from sqlmodel import Session

from orquestra_ai.models import ChatSession


def test_summary_compaction_and_planner(client):
    session_payload = client.post(
        "/api/chat/sessions",
        json={
            "title": "planner-session",
            "objective": "Estruturar um plano de execução com próximos passos reais.",
            "preset": "assistant",
        },
    ).json()
    session_id = session_payload["id"]

    prompts = [
        "Primeiro precisamos consolidar a arquitetura de memória.",
        "Depois validar a compactação de contexto para chats longos.",
        "Por fim criar um workflow local para validação da stack.",
    ]
    for prompt in prompts:
        response = client.post(
            "/api/chat/stream",
            json={"session_id": session_id, "message": prompt, "mock_response": True, "memory_enabled": True},
        )
        assert response.status_code == 200, response.text

    summary = client.get(f"/api/chat/sessions/{session_id}/summary")
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert summary_payload["compaction_state"]["summary_version"] >= 1
    assert isinstance(summary_payload["next_steps"], str)

    compact = client.post(f"/api/chat/sessions/{session_id}/compact")
    assert compact.status_code == 200, compact.text
    compact_payload = compact.json()
    assert compact_payload["compaction_state"]["summary_version"] >= 1

    planner = client.post(f"/api/chat/sessions/{session_id}/planner/rebuild")
    assert planner.status_code == 200, planner.text
    planner_payload = planner.json()
    assert planner_payload["snapshot"]["objective"]
    assert planner_payload["tasks"]

    task = client.post(
        f"/api/chat/sessions/{session_id}/tasks",
        json={"subject": "Executar testes dirigidos", "description": "Cobrir memória, planner e workflow.", "status": "pending"},
    )
    assert task.status_code == 200, task.text
    task_payload = task.json()

    patched = client.patch(
        f"/api/chat/sessions/{session_id}/tasks",
        params={"task_id": task_payload["id"]},
        json={"status": "completed", "metadata": {"updated_from": "pytest"}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"


def test_auto_compact_respects_context_budget(client):
    session_payload = client.post(
        "/api/chat/sessions",
        json={
            "title": "auto-compact",
            "objective": "Preservar continuidade em conversas longas sem transcript integral.",
            "preset": "assistant",
        },
    ).json()
    session_id = session_payload["id"]

    for index in range(8):
        response = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "message": (
                    f"Turno {index}: consolidar arquitetura, memória híbrida, planner, workflow e "
                    "compactação automática com preservação de próximos passos reais."
                ),
                "mock_response": True,
                "memory_enabled": True,
                "compaction_enabled": True,
                "context_budget": 320,
            },
        )
        assert response.status_code == 200, response.text

    with Session(client.app.state.engine) as session:
        chat_session = session.get(ChatSession, session_id)
        assert chat_session is not None
        snapshot = client.app.state.memory_graph.build_context_snapshot(session, chat_session, context_budget=320)

    assert len(snapshot["context_text"]) <= 320
    assert snapshot["compaction_state"]["compacted_message_count"] > 0
    assert snapshot["compaction_state"]["summary_version"] >= 1
    assert snapshot["compaction_state"]["preserved_recent_turns"] >= 2


def test_planner_dependencies_roundtrip_via_api(client):
    session_payload = client.post(
        "/api/chat/sessions",
        json={
            "title": "planner-deps",
            "objective": "Validar dependências entre tarefas persistidas.",
            "preset": "assistant",
        },
    ).json()
    session_id = session_payload["id"]

    prep = client.post(
        f"/api/chat/sessions/{session_id}/tasks",
        json={"subject": "Preparar memória base", "description": "Organizar fatos e referências.", "status": "pending"},
    )
    assert prep.status_code == 200, prep.text
    prep_payload = prep.json()

    execute = client.post(
        f"/api/chat/sessions/{session_id}/tasks",
        json={"subject": "Executar validação final", "description": "Rodar smoke e revisar output.", "status": "pending"},
    )
    assert execute.status_code == 200, execute.text
    execute_payload = execute.json()

    blocked = client.patch(
        f"/api/chat/sessions/{session_id}/tasks",
        params={"task_id": execute_payload["id"]},
        json={"blocked_by": [prep_payload["id"]]},
    )
    assert blocked.status_code == 200, blocked.text

    blocks = client.patch(
        f"/api/chat/sessions/{session_id}/tasks",
        params={"task_id": prep_payload["id"]},
        json={"blocks": [execute_payload["id"]]},
    )
    assert blocks.status_code == 200, blocks.text

    planner = client.get(f"/api/chat/sessions/{session_id}/planner")
    assert planner.status_code == 200, planner.text
    tasks = {item["id"]: item for item in planner.json()["tasks"]}

    assert tasks[execute_payload["id"]]["blocked_by"] == [prep_payload["id"]]
    assert tasks[prep_payload["id"]]["blocks"] == [execute_payload["id"]]
