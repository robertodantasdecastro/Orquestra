#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
else
  PYTHON_BIN="python3"
fi

echo "[orquestra] root: $ROOT_DIR"
echo "[orquestra] python: $($PYTHON_BIN -V 2>&1)"

for cmd in npm cargo; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[orquestra] dependência ausente: $cmd" >&2
    exit 1
  fi
done

if [ ! -d ".venv" ]; then
  echo "[orquestra] criando .venv"
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

if command -v uv >/dev/null 2>&1; then
  echo "[orquestra] instalando dependências Python com uv"
  uv pip install --python .venv/bin/python -r requirements-orquestra.txt
else
  echo "[orquestra] uv indisponível; usando pip"
  python -m pip install --upgrade pip setuptools wheel
  pip install -r requirements-orquestra.txt
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "[orquestra] .env criado a partir de .env.example"
fi

(
  cd orquestra_web
  npm install
)

echo
echo "[orquestra] bootstrap concluído"
echo "[orquestra] próximos passos:"
echo "  1. editar .env se quiser providers reais"
echo "  2. ./scripts/validate_orquestra.sh"
echo "  3. ./scripts/start_orquestra_api.sh"
echo "  4. ./scripts/start_orquestra_web.sh"
