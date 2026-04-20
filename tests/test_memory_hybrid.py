from __future__ import annotations

from pathlib import Path


def test_memory_projection_and_hybrid_recall(client):
    session_payload = client.post(
        "/api/chat/sessions",
        json={
            "title": "memory-hybrid",
            "objective": "Registrar decisões revisáveis e projetar memórias em arquivo.",
            "preset": "research",
            "memory_policy": {"enabled": True, "auto_capture": True, "review_required": True},
            "rag_policy": {"enabled": True, "include_memory": True},
        },
    ).json()
    session_id = session_payload["id"]

    chat = client.post(
        "/api/chat/stream",
        json={
            "session_id": session_id,
            "message": "Definimos que a memória durável precisa ser local-first e revisável.",
            "mock_response": True,
            "memory_enabled": True,
        },
    )
    assert chat.status_code == 200, chat.text

    candidates = client.get("/api/memory/candidates", params={"session_id": session_id, "status": "pending"}).json()
    assert candidates
    assert candidates[0]["memory_kind"] == "reference"

    approved = client.post(
        f"/api/memory/candidates/{candidates[0]['id']}/approve",
        json={"create_training_candidate": False},
    )
    assert approved.status_code == 200, approved.text
    payload = approved.json()
    assert payload["record"]["memory_kind"] == "reference"

    projection_path = Path(payload["projection"]["projection_path"])
    assert projection_path.exists()
    assert "local-first" in projection_path.read_text(encoding="utf-8")

    recall = client.post(
        "/api/memory/recall",
        json={
            "query": "qual decisão local-first foi aprovada?",
            "session_id": session_id,
            "memory_kinds": ["reference"],
            "limit": 5,
        },
    )
    assert recall.status_code == 200, recall.text
    recall_payload = recall.json()
    assert recall_payload["items"]
    assert any(item["memory_kind"] == "reference" for item in recall_payload["items"])
