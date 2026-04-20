from __future__ import annotations


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
