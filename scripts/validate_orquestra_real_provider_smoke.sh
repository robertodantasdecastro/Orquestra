#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROVIDERS=()

usage() {
  cat <<'EOF'
Uso: ./scripts/validate_orquestra_real_provider_smoke.sh --provider <id> [--provider <id>]

Executa um smoke opcional end-to-end contra providers reais via API local do Orquestra.

Opções:
  --provider id   Provider a validar. Pode ser repetido.
  -h, --help      Mostra esta ajuda.

Também aceita:
  ORQUESTRA_VALIDATE_REAL_PROVIDERS=openai,lmstudio
EOF
}

add_provider_list() {
  local raw="$1"
  local normalized
  normalized="${raw//,/ }"
  local item
  for item in $normalized; do
    if [[ -n "$item" ]]; then
      PROVIDERS+=("$item")
    fi
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)
      if [[ $# -lt 2 ]]; then
        echo "[orquestra-provider-smoke] --provider precisa de um id" >&2
        exit 1
      fi
      PROVIDERS+=("$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[orquestra-provider-smoke] argumento desconhecido: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ${#PROVIDERS[@]} -eq 0 && -n "${ORQUESTRA_VALIDATE_REAL_PROVIDERS:-}" ]]; then
  add_provider_list "${ORQUESTRA_VALIDATE_REAL_PROVIDERS}"
fi

if [[ ${#PROVIDERS[@]} -eq 0 ]]; then
  echo "[orquestra-provider-smoke] nenhum provider informado" >&2
  usage >&2
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "[orquestra-provider-smoke] .venv ausente; rode ./scripts/bootstrap_orquestra.sh primeiro" >&2
  exit 1
fi

source .venv/bin/activate

CHECK_ARGS=(--strict)
for provider in "${PROVIDERS[@]}"; do
  CHECK_ARGS+=(--require "$provider")
done

./scripts/check_orquestra_providers.sh "${CHECK_ARGS[@]}"

export ORQUESTRA_PROVIDER_SMOKE_PROVIDERS="$(IFS=,; printf '%s' "${PROVIDERS[*]}")"

PYTHONPATH=. python - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from orquestra_ai.app import create_app
from orquestra_ai.config import load_settings


def parse_sse_events(raw: str) -> list[tuple[str, dict[str, object] | str]]:
    events: list[tuple[str, dict[str, object] | str]] = []
    event_name: str | None = None
    data_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("event:"):
            if event_name is not None:
                payload_text = "\n".join(data_lines)
                try:
                    payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    payload = payload_text
                events.append((event_name, payload))
                data_lines = []
            event_name = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
            continue
        if not line.strip() and event_name is not None:
            payload_text = "\n".join(data_lines)
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                payload = payload_text
            events.append((event_name, payload))
            event_name = None
            data_lines = []
    if event_name is not None:
        payload_text = "\n".join(data_lines)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = payload_text
        events.append((event_name, payload))
    return events


provider_ids = [item.strip() for item in os.environ.get("ORQUESTRA_PROVIDER_SMOKE_PROVIDERS", "").split(",") if item.strip()]
if not provider_ids:
    raise SystemExit("ORQUESTRA_PROVIDER_SMOKE_PROVIDERS vazio")

root = Path.cwd()
app = create_app(load_settings(root))

with TestClient(app) as client:
    providers_response = client.get("/api/providers")
    assert providers_response.status_code == 200, providers_response.text
    providers_payload = {item["provider_id"]: item for item in providers_response.json()}

    for provider_id in provider_ids:
        provider = providers_payload.get(provider_id)
        assert provider is not None, f"provider ausente no cadastro: {provider_id}"
        assert provider.get("enabled", True), f"provider desabilitado: {provider_id}"
        model_name = str(provider.get("default_model") or "unknown-model")

        session_response = client.post(
            "/api/chat/sessions",
            json={
                "title": f"provider-smoke-{provider_id}",
                "objective": f"Validar provider real {provider_id} sem modo mock.",
                "preset": "assistant",
                "provider_id": provider_id,
                "model_name": model_name,
                "memory_policy": {"enabled": False, "auto_capture": False, "review_required": True},
                "rag_policy": {
                    "enabled": False,
                    "include_memory": False,
                    "include_workspace": False,
                    "include_sources": False,
                    "collections": [],
                },
            },
        )
        assert session_response.status_code == 200, session_response.text
        session_id = session_response.json()["id"]

        response = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "message": "Responda apenas com OK.",
                "provider_id": provider_id,
                "model_name": model_name,
                "mock_response": False,
                "temperature": 0,
                "max_tokens": 24,
                "memory_enabled": False,
                "include_workspace": False,
                "include_sources": False,
                "planner_enabled": False,
                "task_context_enabled": False,
                "compaction_enabled": True,
                "context_budget": 2000,
            },
        )
        assert response.status_code == 200, response.text
        events = parse_sse_events(response.text)
        done_payload = None
        for event_name, payload in events:
            if event_name == "done" and isinstance(payload, dict):
                done_payload = payload
                break
        assert done_payload is not None, f"stream sem evento done para {provider_id}"
        assert done_payload.get("provider_id") == provider_id, done_payload
        assert done_payload.get("model_name"), done_payload
        print(
            f"[orquestra-provider-smoke] provider={provider_id} model={done_payload['model_name']} "
            f"latency={done_payload.get('latency_seconds')}"
        )
PY

echo "[orquestra-provider-smoke] smoke real concluído"
