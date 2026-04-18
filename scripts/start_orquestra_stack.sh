#!/bin/bash
set -euo pipefail

ROOT_DIR="${HOME}/Desenvolvimento/Orquestra"
if [ ! -d "${ROOT_DIR}" ]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "${ROOT_DIR}"

tmux kill-session -t orquestra-api 2>/dev/null || true
tmux kill-session -t orquestra-web 2>/dev/null || true

tmux new-session -d -s orquestra-api "cd '${ROOT_DIR}' && ./scripts/start_orquestra_api.sh >> logs/orquestra_api.log 2>&1"
tmux new-session -d -s orquestra-web "cd '${ROOT_DIR}' && ./scripts/start_orquestra_web.sh >> logs/orquestra_web.log 2>&1"

echo "Orquestra API: http://127.0.0.1:${ORQUESTRA_API_PORT:-8808}"
echo "Orquestra Web: http://127.0.0.1:4177"
