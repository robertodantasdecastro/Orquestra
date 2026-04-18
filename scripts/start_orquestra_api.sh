#!/bin/bash
set -euo pipefail

ROOT_DIR="${HOME}/Desenvolvimento/Orquestra"
if [ ! -d "${ROOT_DIR}" ]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "${ROOT_DIR}"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
elif [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
export ORQUESTRA_API_HOST="${ORQUESTRA_API_HOST:-127.0.0.1}"
export ORQUESTRA_API_PORT="${ORQUESTRA_API_PORT:-8808}"

python3 -m uvicorn orquestra_ai.app:app --host "${ORQUESTRA_API_HOST}" --port "${ORQUESTRA_API_PORT}" --reload
