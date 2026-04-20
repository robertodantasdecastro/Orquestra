#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "[orquestra] .venv ausente; rode ./scripts/bootstrap_orquestra.sh primeiro" >&2
  exit 1
fi

source .venv/bin/activate
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION="${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}"

echo "[orquestra] py_compile"
python -m py_compile orquestra_ai/*.py rag/*.py training/local/*.py

echo "[orquestra] pytest"
PYTHONPATH=. pytest -q

echo "[orquestra] shell syntax"
bash -n scripts/*.sh

echo "[orquestra] frontend build"
(
  cd orquestra_web
  ./node_modules/.bin/vitest run --environment jsdom
  ./node_modules/.bin/tsc -b
  ./node_modules/.bin/vite build
)

echo "[orquestra] tauri cargo check"
(
  cd orquestra_web/src-tauri
  cargo check
)

PACKAGE_VERSION="$(/usr/bin/python3 - <<'PY' "${ROOT_DIR}/orquestra_web/package.json"
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(str(payload.get("version", "0.2.0")))
PY
)"
APP_BUNDLE="orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app"
DMG_BUNDLE="orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_${PACKAGE_VERSION}_aarch64.dmg"
if [[ -d "${APP_BUNDLE}" && -f "${DMG_BUNDLE}" ]]; then
  echo "[orquestra] macOS package validation"
  ./scripts/validate_orquestra_macos_package.sh
else
  echo "[orquestra] macOS package validation skipped (rode npm run desktop:build para gerar .app/.dmg)"
fi

echo "[orquestra] api smoke"
PYTHONPATH=. python - <<'PY'
from pathlib import Path
from fastapi.testclient import TestClient
from orquestra_ai.app import create_app
from orquestra_ai.config import load_settings

root = Path.cwd()
app = create_app(load_settings(root))

with TestClient(app) as client:
    health = client.get("/api/health")
    assert health.status_code == 200, health.text
    health_payload = health.json()
    assert health_payload["app_version"], "health sem versão de app"
    assert "runtime" in health_payload, "health sem bloco de runtime"
    assert health_payload["schema_version"] == health_payload["schema_target_version"], "schema fora da versão alvo"
    assert health_payload["migration_required"] is False, "migration_required deveria estar falso após bootstrap"

    session_obj = client.post(
        "/api/chat/sessions",
        json={
            "title": "validation-smoke",
            "objective": "Validar memória associada ao RAG em modo local-first.",
            "preset": "research",
            "memory_policy": {"enabled": True, "auto_capture": True, "review_required": True},
            "rag_policy": {"enabled": True, "include_memory": True, "include_workspace": True},
        },
    ).json()
    session_id = session_obj["id"]

    profile = client.get(f"/api/chat/sessions/{session_id}/profile")
    assert profile.status_code == 200, profile.text
    assert profile.json()["objective"], "perfil de sessão sem objetivo"

    chat = client.post(
        "/api/chat/stream",
        json={"session_id": session_id, "message": "oi", "mock_response": True, "memory_enabled": True},
    )
    assert chat.status_code == 200, chat.text

    memory_candidates = client.get("/api/memory/candidates", params={"session_id": session_id, "status": "pending"})
    assert memory_candidates.status_code == 200, memory_candidates.text
    candidate_rows = memory_candidates.json()
    assert candidate_rows, "chat mock não gerou candidato revisável"

    approve = client.post(f"/api/memory/candidates/{candidate_rows[0]['id']}/approve", json={"create_training_candidate": False})
    assert approve.status_code == 200, approve.text
    assert approve.json()["record"]["scope"], "aprovação não criou MemoryRecord"

    rag = client.post(
        "/api/rag/query",
        json={"session_id": session_id, "question": "qual memoria foi aprovada?", "mock_llm": True, "memory_enabled": True},
    )
    assert rag.status_code == 200, rag.text

    summary = client.get(f"/api/chat/sessions/{session_id}/summary")
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert "compaction_state" in summary_payload, "summary sem compaction_state"

    compact = client.post(f"/api/chat/sessions/{session_id}/compact")
    assert compact.status_code == 200, compact.text

    planner = client.post(f"/api/chat/sessions/{session_id}/planner/rebuild")
    assert planner.status_code == 200, planner.text
    planner_payload = planner.json()
    assert planner_payload["tasks"], "planner não gerou tasks"

    task = client.post(
        f"/api/chat/sessions/{session_id}/tasks",
        json={"subject": "Executar workflow de validação", "description": "Cobrir shell seguro e rag query mockada."},
    )
    assert task.status_code == 200, task.text

    workflow = client.post(
        "/api/workflows/runs",
        json={
            "session_id": session_id,
            "workflow_name": "validate-smoke",
            "summary": "Workflow local de smoke",
            "steps": [
                {"step_type": "shell_safe", "label": "Git diff", "payload": {"command": "git diff --check"}},
                {
                    "step_type": "rag_query",
                    "label": "RAG mock",
                    "payload": {
                        "question": "Qual é o objetivo da sessão de validação?",
                        "session_id": session_id,
                        "mock_llm": True,
                        "memory_enabled": True,
                    },
                },
            ],
        },
    )
    assert workflow.status_code == 200, workflow.text
    workflow_id = workflow.json()["id"]

    import time

    final_workflow = None
    for _ in range(120):
        current = client.get(f"/api/workflows/runs/{workflow_id}")
        assert current.status_code == 200, current.text
        final_workflow = current.json()
        if final_workflow["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            break
        time.sleep(0.25)

    assert final_workflow is not None, "workflow sem payload final"
    assert final_workflow["status"] == "succeeded", final_workflow
    assert len(final_workflow["steps"]) == 2, final_workflow
    assert [step["status"] for step in final_workflow["steps"]] == ["succeeded", "succeeded"], final_workflow

    resume = client.post(f"/api/chat/sessions/{session_id}/resume")
    assert resume.status_code == 200, resume.text

    transcript = client.get(f"/api/chat/sessions/{session_id}/transcript")
    assert transcript.status_code == 200, transcript.text

    scan = client.post(
        "/api/workspace/attach-directory",
        json={"root_path": str(root / "rag" / "samples"), "recursive": True},
    )
    assert scan.status_code == 200, scan.text
    scan_payload = scan.json()

    assets = client.get("/api/workspace/assets", params={"scan_id": scan_payload["id"]})
    assert assets.status_code == 200, assets.text
    asset_rows = assets.json()
    assert asset_rows, "nenhum asset encontrado no scan de validação"

    first_asset = asset_rows[0]["id"]
    extract = client.post(f"/api/workspace/assets/{first_asset}/extract", json={"mode": "auto"})
    assert extract.status_code == 200, extract.text

    preview = client.get(f"/api/workspace/assets/{first_asset}/preview")
    assert preview.status_code == 200, preview.text

    memorize = client.post(
        f"/api/workspace/assets/{first_asset}/memorize",
        json={"scope": "project_memory", "title": "validation-smoke"},
    )
    assert memorize.status_code == 200, memorize.text

    training_candidates = client.get("/api/memory/training-candidates")
    assert training_candidates.status_code == 200, training_candidates.text

print("ORQUESTRA_VALIDATE_OK")
PY

echo "[orquestra] validação concluída"
