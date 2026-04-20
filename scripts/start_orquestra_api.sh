#!/bin/bash
set -euo pipefail

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

cd "${ROOT_DIR}"

PYTHON_BIN="python3"
if [ -x "${ROOT_DIR}/.venv/bin/python3" ]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
elif [ -x "${ROOT_DIR}/.venv/bin/python" ]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif [ -x "${ROOT_DIR}/venv/bin/python3" ]; then
  PYTHON_BIN="${ROOT_DIR}/venv/bin/python3"
elif [ -x "${ROOT_DIR}/venv/bin/python" ]; then
  PYTHON_BIN="${ROOT_DIR}/venv/bin/python"
fi

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
export ORQUESTRA_API_HOST="${ORQUESTRA_API_HOST:-127.0.0.1}"
export ORQUESTRA_API_PORT="${ORQUESTRA_API_PORT:-8808}"
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION="${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}"
export PATH="${ROOT_DIR}/.venv/bin:${ROOT_DIR}/venv/bin:${PATH}"

exec "${PYTHON_BIN}" -m uvicorn orquestra_ai.app:app --host "${ORQUESTRA_API_HOST}" --port "${ORQUESTRA_API_PORT}"
