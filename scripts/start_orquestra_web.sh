#!/bin/bash
set -euo pipefail

ROOT_DIR="${HOME}/Desenvolvimento/Orquestra"
if [ ! -d "${ROOT_DIR}" ]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "${ROOT_DIR}/orquestra_web"

if [ ! -d "node_modules" ]; then
  npm install
fi

npm run dev -- --host 127.0.0.1 --port 4177
