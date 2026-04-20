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
export TRAINPLANE_HOST="${TRAINPLANE_HOST:-127.0.0.1}"
export TRAINPLANE_PORT="${TRAINPLANE_PORT:-8818}"
export TRAINPLANE_PUBLIC_BASE_URL="${TRAINPLANE_PUBLIC_BASE_URL:-http://${TRAINPLANE_HOST}:${TRAINPLANE_PORT}}"
export PATH="${ROOT_DIR}/.venv/bin:${ROOT_DIR}/venv/bin:${PATH}"

exec "${PYTHON_BIN}" -m uvicorn orquestra_trainplane.app:create_app --factory --host "${TRAINPLANE_HOST}" --port "${TRAINPLANE_PORT}"
