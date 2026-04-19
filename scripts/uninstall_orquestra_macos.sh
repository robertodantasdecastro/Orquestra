#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-uninstall] este desinstalador é apenas para macOS" >&2
  exit 1
fi

PURGE_DATA="false"
if [[ "${1:-}" == "--purge-data" ]]; then
  PURGE_DATA="true"
fi

APP_NAME="Orquestra AI.app"
INSTALL_DIR="${ORQUESTRA_INSTALL_DIR:-$HOME/Applications/$APP_NAME}"
SUPPORT_DIR="${HOME}/Library/Application Support/Orquestra"
LOG_DIR="${HOME}/Library/Logs/Orquestra"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LAUNCH_AGENT_LABEL="ai.orquestra.api"
LAUNCH_AGENT_PLIST="${LAUNCH_AGENTS_DIR}/${LAUNCH_AGENT_LABEL}.plist"

echo "[orquestra-uninstall] removendo LaunchAgent"
launchctl bootout "gui/${UID}" "${LAUNCH_AGENT_PLIST}" >/dev/null 2>&1 || true
rm -f "${LAUNCH_AGENT_PLIST}"

echo "[orquestra-uninstall] removendo app instalado"
rm -rf "${INSTALL_DIR}"

if [[ "${PURGE_DATA}" == "true" ]]; then
  echo "[orquestra-uninstall] removendo dados locais do usuário"
  rm -rf "${SUPPORT_DIR}" "${LOG_DIR}"
else
  echo "[orquestra-uninstall] preservando dados locais em ${SUPPORT_DIR} e ${LOG_DIR}"
fi

echo
echo "[orquestra-uninstall] desinstalação concluída"
echo "  app removido: ${INSTALL_DIR}"
echo "  launch agent removido: ${LAUNCH_AGENT_PLIST}"
if [[ "${PURGE_DATA}" == "true" ]]; then
  echo "  dados removidos"
else
  echo "  dados preservados"
fi
