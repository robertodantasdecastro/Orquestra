#!/bin/bash
set -euo pipefail

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

cd "${ROOT_DIR}/orquestra_web"

if [ ! -d "node_modules" ]; then
  npm install --no-audit --no-fund
fi

./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
