#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-uninstall] este desinstalador é apenas para macOS" >&2
  exit 1
fi

PURGE_DATA="false"
REMOVE_LAUNCH_AGENT="true"
APP_NAME="Orquestra AI.app"
APP_PROCESS_NAME="orquestra-desktop"
INSTALL_DIR="${ORQUESTRA_INSTALL_DIR:-$HOME/Applications/$APP_NAME}"
SUPPORT_DIR="${HOME}/Library/Application Support/Orquestra"
LOG_DIR="${HOME}/Library/Logs/Orquestra"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LAUNCH_AGENT_LABEL="ai.orquestra.api"
LAUNCH_AGENT_PLIST="${LAUNCH_AGENTS_DIR}/${LAUNCH_AGENT_LABEL}.plist"

usage() {
  cat <<USAGE
Uso: ./scripts/uninstall_orquestra_macos.sh [opcoes]

Opcoes:
  --purge-data       Remove tambem dados de suporte e logs do usuario.
  --no-launch-agent  Remove apenas o app informado, preservando o LaunchAgent.
  --install-dir PATH Define o .app instalado a remover.
  -h, --help         Mostra esta ajuda.

Por padrao, a desinstalacao remove o app e o LaunchAgent, mas preserva
~/Library/Application Support/Orquestra e ~/Library/Logs/Orquestra.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge-data)
      PURGE_DATA="true"
      shift
      ;;
    --no-launch-agent)
      REMOVE_LAUNCH_AGENT="false"
      shift
      ;;
    --install-dir)
      INSTALL_DIR="${2:-}"
      if [[ -z "${INSTALL_DIR}" ]]; then
        echo "[orquestra-uninstall] --install-dir exige um caminho" >&2
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[orquestra-uninstall] opcao invalida: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ "${REMOVE_LAUNCH_AGENT}" == "true" ]]; then
  echo "[orquestra-uninstall] removendo LaunchAgent"
  launchctl bootout "gui/${UID}" "${LAUNCH_AGENT_PLIST}" >/dev/null 2>&1 || true
  rm -f "${LAUNCH_AGENT_PLIST}"
else
  echo "[orquestra-uninstall] preservando LaunchAgent (--no-launch-agent)"
fi

echo "[orquestra-uninstall] encerrando app desktop se estiver aberto"
pkill -x "${APP_PROCESS_NAME}" >/dev/null 2>&1 || true

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
if [[ "${REMOVE_LAUNCH_AGENT}" == "true" ]]; then
  echo "  launch agent removido: ${LAUNCH_AGENT_PLIST}"
else
  echo "  launch agent preservado: ${LAUNCH_AGENT_PLIST}"
fi
if [[ "${PURGE_DATA}" == "true" ]]; then
  echo "  dados removidos"
else
  echo "  dados preservados"
fi
