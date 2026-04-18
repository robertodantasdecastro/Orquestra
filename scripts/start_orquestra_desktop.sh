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
export VITE_ORQUESTRA_API_BASE="http://${ORQUESTRA_API_HOST}:${ORQUESTRA_API_PORT}"

./scripts/start_orquestra_api.sh >/tmp/orquestra_api_desktop.log 2>&1 &
API_PID=$!

cleanup() {
  kill "${API_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sleep 2
cd "${ROOT_DIR}/orquestra_web"
npm run desktop:dev
