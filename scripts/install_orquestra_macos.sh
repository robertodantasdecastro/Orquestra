#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-install] este instalador é apenas para macOS" >&2
  exit 1
fi

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_NAME="Orquestra AI.app"
INSTALL_DIR="${ORQUESTRA_INSTALL_DIR:-$HOME/Applications/$APP_NAME}"
APP_SOURCE="${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/macos/${APP_NAME}"
SUPPORT_DIR="${HOME}/Library/Application Support/Orquestra"
LOG_DIR="${HOME}/Library/Logs/Orquestra"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LAUNCH_AGENT_LABEL="ai.orquestra.api"
LAUNCH_AGENT_PLIST="${LAUNCH_AGENTS_DIR}/${LAUNCH_AGENT_LABEL}.plist"
API_URL="http://127.0.0.1:${ORQUESTRA_API_PORT:-8808}/api/health"

mkdir -p "${HOME}/Applications" "${SUPPORT_DIR}" "${LOG_DIR}" "${LAUNCH_AGENTS_DIR}"

echo "[orquestra-install] root: ${ROOT_DIR}"
echo "[orquestra-install] preparando ambiente local"
"${ROOT_DIR}/scripts/bootstrap_orquestra.sh"

echo "[orquestra-install] gerando app desktop"
(
  cd "${ROOT_DIR}/orquestra_web"
  npm run desktop:build
)

if [[ ! -d "${APP_SOURCE}" ]]; then
  echo "[orquestra-install] app bundle ausente: ${APP_SOURCE}" >&2
  exit 1
fi

echo "[orquestra-install] instalando app em ${INSTALL_DIR}"
rm -rf "${INSTALL_DIR}"
cp -R "${APP_SOURCE}" "${INSTALL_DIR}"

cat > "${LAUNCH_AGENT_PLIST}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LAUNCH_AGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>./scripts/start_orquestra_api.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ORQUESTRA_ROOT</key>
    <string>${ROOT_DIR}</string>
    <key>PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION</key>
    <string>python</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/api.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/api.stderr.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/${UID}" "${LAUNCH_AGENT_PLIST}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID}" "${LAUNCH_AGENT_PLIST}"
launchctl kickstart -k "gui/${UID}/${LAUNCH_AGENT_LABEL}" >/dev/null 2>&1 || true

echo "[orquestra-install] aguardando API local"
ATTEMPTS=30
for ((i = 1; i <= ATTEMPTS; i++)); do
  if curl -fsS "${API_URL}" >/dev/null 2>&1; then
    echo "[orquestra-install] API pronta em ${API_URL}"
    break
  fi
  if [[ "${i}" -eq "${ATTEMPTS}" ]]; then
    echo "[orquestra-install] a API não respondeu após a instalação" >&2
    exit 1
  fi
  sleep 1
done

echo
echo "[orquestra-install] instalação concluída"
echo "  app: ${INSTALL_DIR}"
echo "  launch agent: ${LAUNCH_AGENT_PLIST}"
echo "  logs: ${LOG_DIR}"
echo "  api: ${API_URL}"
