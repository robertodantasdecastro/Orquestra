#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Orquestra AI"
APP_PROCESS_NAME="orquestra-desktop"
APP_BUNDLE="${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/macos/${APP_NAME}.app"
API_URL="http://127.0.0.1:${ORQUESTRA_API_PORT:-8808}/api/health"
API_PID_FILE="${ROOT_DIR}/experiments/orquestra/orquestra-api.pid"

cd "${ROOT_DIR}"

stop_app() {
  pkill -x "${APP_PROCESS_NAME}" >/dev/null 2>&1 || true
}

ensure_api() {
  if curl -fsS "${API_URL}" >/dev/null 2>&1; then
    return
  fi
  mkdir -p "$(dirname "${API_PID_FILE}")"
  ./scripts/start_orquestra_api.sh >"${ROOT_DIR}/experiments/orquestra/api.desktop.stdout.log" 2>"${ROOT_DIR}/experiments/orquestra/api.desktop.stderr.log" &
  echo "$!" >"${API_PID_FILE}"
  for _ in {1..30}; do
    if curl -fsS "${API_URL}" >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done
  echo "[orquestra-run] API não respondeu em ${API_URL}" >&2
  exit 1
}

build_app() {
  (
    cd "${ROOT_DIR}/orquestra_web"
    npm run desktop:build
  )
}

open_app() {
  ensure_api
  if [[ ! -d "${APP_BUNDLE}" ]]; then
    echo "[orquestra-run] app bundle ausente: ${APP_BUNDLE}" >&2
    echo "[orquestra-run] rode sem --skip-build para gerar o desktop." >&2
    exit 1
  fi
  /usr/bin/open -n "${APP_BUNDLE}"
}

case "${MODE}" in
  run)
    stop_app
    build_app
    open_app
    ;;
  --skip-build|skip-build)
    stop_app
    open_app
    ;;
  --verify|verify)
    stop_app
    build_app
    ./scripts/validate_orquestra_macos_package.sh
    open_app
    for _ in {1..10}; do
      if pgrep -x "${APP_PROCESS_NAME}" >/dev/null; then
        break
      fi
      sleep 1
    done
    pgrep -x "${APP_PROCESS_NAME}" >/dev/null
    curl -fsS "${API_URL}" >/dev/null
    echo "[orquestra-run] app e API verificados"
    ;;
  --logs|logs)
    stop_app
    build_app
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"${APP_PROCESS_NAME}\""
    ;;
  --telemetry|telemetry)
    stop_app
    build_app
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"${APP_PROCESS_NAME}\" OR process == \"Python\""
    ;;
  --debug|debug)
    stop_app
    build_app
    ensure_api
    lldb -- "${APP_BUNDLE}/Contents/MacOS/${APP_PROCESS_NAME}"
    ;;
  *)
    echo "usage: $0 [run|--skip-build|--verify|--logs|--telemetry|--debug]" >&2
    exit 2
    ;;
esac
