from __future__ import annotations

import json

from sqlmodel import Session, select

from orquestra_ai.models import ChatMessage


def test_osint_connectors_are_seeded_and_admin_toggle_works(client):
    connectors = client.get("/api/osint/connectors").json()
    assert connectors
    brave = next(item for item in connectors if item["connector_id"] == "brave")
    assert brave["enabled_global"] is True

    disabled = client.post("/api/osint/connectors/brave/disable")
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled_global"] is False

    enabled = client.post("/api/osint/connectors/brave/enable")
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["enabled_global"] is True


def test_osint_claim_approval_preserves_provenance_and_feeds_rag(client, monkeypatch):
    project_id = client.get("/api/projects").json()[0]["id"]
    session_payload = client.post(
        "/api/chat/sessions",
        json={
            "project_id": project_id,
            "title": "osint-rag-session",
            "objective": "Correlacionar evidências web com memória aprovada.",
            "preset": "osint",
            "memory_policy": {"enabled": True, "auto_capture": True, "review_required": True},
            "rag_policy": {"enabled": True, "include_memory": True, "include_sources": True},
        },
    ).json()

    investigation = client.post(
        "/api/osint/investigations",
        json={
            "project_id": project_id,
            "session_id": session_payload["id"],
            "title": "Investigação Manual",
            "objective": "Validar evidência rastreável no Orquestra.",
            "target_entity": "Orquestra AI",
        },
    ).json()

    registry_entry = client.post(
        "/api/osint/source-registry",
        json={
            "source_key": "manual-orquestra-seed",
            "connector_id": "onion_manual",
            "title": "Manual Orquestra Seed",
            "category": "manual_seed",
            "access_type": "web",
            "base_url": "https://example.test/orquestra",
            "description": "Orquestra AI usa memory graph local-first com aprovação explícita.",
        },
    ).json()

    search_response = client.post(
        f"/api/osint/investigations/{investigation['id']}/search",
        json={
            "query": "orquestra ai memory graph local-first",
            "connector_ids": ["onion_manual"],
            "source_registry_ids": [registry_entry["id"]],
        },
    )
    assert search_response.status_code == 200, search_response.text
    search_payload = search_response.json()
    assert search_payload["results"]
    source_id = search_payload["results"][0]["id"]

    def fake_fetch_url(url: str, *, via_tor: bool, follow_same_host_redirects_only: bool):
        return (
            (
                b"<html><head><title>Orquestra Evidence</title></head>"
                b"<body>Orquestra AI maintains a local-first memory graph and promotes approved OSINT claims.</body></html>"
            ),
            {"content-type": "text/html; charset=utf-8"},
        )

    monkeypatch.setattr(client.app.state.osint_service, "_fetch_url", fake_fetch_url)

    fetch_response = client.post(
        f"/api/osint/investigations/{investigation['id']}/fetch",
        json={"source_id": source_id},
    )
    assert fetch_response.status_code == 200, fetch_response.text
    fetch_payload = fetch_response.json()
    assert fetch_payload["evidence"]
    assert fetch_payload["claims"]

    claim_id = fetch_payload["claims"][0]["id"]
    approved_claim = client.post(f"/api/osint/claims/{claim_id}/approve", json={"create_memory": True})
    assert approved_claim.status_code == 200, approved_claim.text
    approved_payload = approved_claim.json()

    memory_record = approved_payload["memory_record"]
    assert memory_record is not None
    assert memory_record["metadata"]["channel"] == "osint"
    assert memory_record["metadata"]["source_url"] == "https://example.test/orquestra"
    assert memory_record["metadata"]["claim_id"] == claim_id
    assert memory_record["metadata"]["evidence_ids"]
    assert approved_payload["projection"]["projection_path"]

    rag_response = client.post(
        "/api/rag/query",
        json={
            "question": "qual evidência aprovada diz que o Orquestra usa memory graph local-first?",
            "project_id": project_id,
            "session_id": session_payload["id"],
            "mock_llm": True,
            "include_osint_evidence": True,
            "investigation_id": investigation["id"],
        },
    )
    assert rag_response.status_code == 200, rag_response.text
    rag_payload = rag_response.json()
    assert rag_payload["osint"]["evidence"]
    assert any((citation.get("channel") or "").startswith("osint") for citation in rag_payload["citations"])


def test_chat_stream_persists_osint_bundle_in_message_metadata(client, monkeypatch):
    session_payload = client.post(
        "/api/chat/sessions",
        json={
            "title": "osint-chat",
            "objective": "Responder com evidência OSINT no chat.",
            "preset": "osint",
            "memory_policy": {"enabled": True, "auto_capture": True, "review_required": True},
            "rag_policy": {"enabled": True, "include_memory": True, "include_sources": True},
        },
    ).json()

    def fake_context_bundle(*args, **kwargs):
        return {
            "investigation_id": "investigation-1",
            "context": "- [evidence] Orquestra Evidence: fonte validada para sessão OSINT (https://example.test/orquestra)",
            "citations": [
                {
                    "channel": "osint_evidence",
                    "source": "https://example.test/orquestra",
                    "title": "Orquestra Evidence",
                    "evidence_id": "evidence-1",
                }
            ],
            "evidence": [
                {
                    "id": "evidence-1",
                    "title": "Orquestra Evidence",
                    "content": "fonte validada para sessão OSINT",
                    "validation_status": "approved",
                    "source_quality": 0.82,
                    "entity_ids": [],
                    "claim_ids": [],
                    "metadata": {"url": "https://example.test/orquestra"},
                }
            ],
            "fresh_results": [],
            "status": "ok",
            "selector_mode": "osint_hybrid",
        }

    monkeypatch.setattr(client.app.state.osint_service, "build_context_bundle", fake_context_bundle)

    response = client.post(
        "/api/chat/stream",
        json={
            "session_id": session_payload["id"],
            "message": "resuma o estado atual com base na evidência OSINT aprovada",
            "mock_response": True,
            "osint_mode": True,
            "evidence_enabled": True,
            "investigation_id": "investigation-1",
        },
    )
    assert response.status_code == 200, response.text
    assert "event: done" in response.text

    with Session(client.app.state.engine) as session:
        assistant_messages = session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_payload["id"])
            .where(ChatMessage.role == "assistant")
            .order_by(ChatMessage.created_at.desc())
        ).all()
        assert assistant_messages
        metadata = json.loads(assistant_messages[0].metadata_json or "{}")

    assert metadata["osint_bundle"]["investigation_id"] == "investigation-1"
    assert metadata["osint_bundle"]["citations"][0]["channel"] == "osint_evidence"
