#!/bin/bash
set -euo pipefail

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

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
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION="${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}"

python3 -m uvicorn orquestra_ai.app:app --host "${ORQUESTRA_API_HOST}" --port "${ORQUESTRA_API_PORT}"
