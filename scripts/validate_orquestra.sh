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

echo "[orquestra] shell syntax"
bash -n scripts/*.sh

echo "[orquestra] frontend build"
(
  cd orquestra_web
  ./node_modules/.bin/tsc -b
  ./node_modules/.bin/vite build
)

echo "[orquestra] tauri cargo check"
(
  cd orquestra_web/src-tauri
  cargo check
)

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

    session_obj = client.post("/api/chat/sessions", json={"title": "validation-smoke"}).json()
    session_id = session_obj["id"]

    chat = client.post(
        "/api/chat/stream",
        json={"session_id": session_id, "message": "oi", "mock_response": True},
    )
    assert chat.status_code == 200, chat.text

    summary = client.get(f"/api/chat/sessions/{session_id}/summary")
    assert summary.status_code == 200, summary.text

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
