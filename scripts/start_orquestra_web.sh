#!/bin/bash
set -euo pipefail

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

cd "${ROOT_DIR}/orquestra_web"

if [ ! -d "node_modules" ]; then
  npm install --no-audit --no-fund
fi

./node_modules/.bin/vite --host 127.0.0.1 --port 4177
