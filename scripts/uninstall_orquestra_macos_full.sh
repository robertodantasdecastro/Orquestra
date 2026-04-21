#!/usr/bin/env bash
set -euo pipefail

MODE="safe"
DRY_RUN="false"
ASSUME_YES="false"
SELECTED_RAW=""
BACKUP_MODE="ask"
CONFIRM_REMOVE_ALL="false"
JSON_MODE="false"
PLAN_FILE=""
EMIT_EVENTS="false"

APP_NAME="Orquestra AI.app"
APP_SHORTCUT_NAME="Orquestra.app"
UNINSTALLER_NAME="Orquestra Uninstaller.app"
APP_PROCESS_NAME="orquestra-desktop"
INSTALL_DIR="${ORQUESTRA_INSTALL_DIR:-$HOME/Applications/$APP_NAME}"
APP_SHORTCUT_PATH="${ORQUESTRA_APP_SHORTCUT_PATH:-$HOME/Applications/$APP_SHORTCUT_NAME}"
UNINSTALLER_INSTALL_DIR="${ORQUESTRA_UNINSTALLER_INSTALL_DIR:-$HOME/Applications/$UNINSTALLER_NAME}"
SUPPORT_DIR="${HOME}/Library/Application Support/Orquestra"
RUNTIME_DIR="${SUPPORT_DIR}/runtime"
LOG_DIR="${HOME}/Library/Logs/Orquestra"
LAUNCH_AGENT_PLIST="${HOME}/Library/LaunchAgents/ai.orquestra.api.plist"
INSTALL_BACKUP_DIR="${RUNTIME_DIR}/experiments/orquestra/install/backups"

usage() {
  cat <<'USAGE'
Uso: ./scripts/uninstall_orquestra_macos_full.sh [opcoes]

Desinstalador seletivo do Orquestra para macOS.

Opcoes:
  --mode safe|all|preserve-deps  Modo de remocao. Padrao: safe.
  --select lista                 Remove apenas itens selecionados por id.
  --dry-run                      Mostra o que seria removido, sem apagar.
  --yes                          Assume confirmacoes simples.
  --backup-data                  Cria backup antes de remover dados sensiveis.
  --no-backup                    Nao cria backup.
  --confirm-remove-all           Confirma modo all em execucao nao interativa.
  --json                         Emite contrato JSON machine-readable em dry-run.
  --plan-file path               Salva plano JSON para UI grafica.
  --emit-events                  Emite eventos JSONL simples para UI grafica.
  --no-tty                       Alias seguro para execucao sem prompt interativo.
  --no-secrets-output            Garante que segredos nunca sejam impressos.
  -h, --help                     Mostra esta ajuda.

Ids principais:
  app,app_shortcut,uninstaller_app,launch_agent,runtime_all,logs,db,memory,rag_indexes,osint,workspace,
  workflows,operations,trainplane,install_backups,runtime_venv

Ids de dependencias globais:
  brew_python,brew_node,brew_rust,brew_uv,brew_ffmpeg,brew_tor,brew_ollama,
  cask_brave,cask_lmstudio
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --select)
      SELECTED_RAW="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --yes)
      ASSUME_YES="true"
      shift
      ;;
    --backup-data)
      BACKUP_MODE="yes"
      shift
      ;;
    --no-backup)
      BACKUP_MODE="no"
      shift
      ;;
    --confirm-remove-all)
      CONFIRM_REMOVE_ALL="true"
      shift
      ;;
    --json)
      JSON_MODE="true"
      shift
      ;;
    --plan-file)
      PLAN_FILE="${2:-}"
      shift 2
      ;;
    --emit-events)
      EMIT_EVENTS="true"
      shift
      ;;
    --no-tty|--no-secrets-output)
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[orquestra-full-uninstall] argumento desconhecido: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${JSON_MODE}" == "true" && "${DRY_RUN}" == "true" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" uninstall-plan --mode "${MODE}"
  exit 0
fi

if [[ -n "${PLAN_FILE}" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" uninstall-plan --mode "${MODE}" > "${PLAN_FILE}"
fi

if [[ "${EMIT_EVENTS}" == "true" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" emit-smoke
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-full-uninstall] este desinstalador e apenas para macOS" >&2
  exit 1
fi

case "${MODE}" in
  safe|all|preserve-deps)
    ;;
  *)
    echo "[orquestra-full-uninstall] modo invalido: ${MODE}" >&2
    exit 2
    ;;
esac

prompt_yes() {
  local question="$1"
  if [[ "${ASSUME_YES}" == "true" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    return 1
  fi
  local answer
  printf '%s [s/N] ' "${question}"
  read -r answer
  case "${answer}" in
    s|S|sim|SIM|y|Y|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

contains_item() {
  local target="$1"
  local list="$2"
  local normalized
  normalized=",${list// /},"
  [[ "${normalized}" == *",${target},"* ]]
}

append_item() {
  local item="$1"
  local list="$2"
  if contains_item "${item}" "${list}"; then
    printf '%s' "${list}"
  elif [[ -z "${list}" ]]; then
    printf '%s' "${item}"
  else
    printf '%s,%s' "${list}" "${item}"
  fi
}

item_path() {
  case "$1" in
    app) printf '%s' "${INSTALL_DIR}" ;;
    app_shortcut) printf '%s' "${APP_SHORTCUT_PATH}" ;;
    uninstaller_app) printf '%s' "${UNINSTALLER_INSTALL_DIR}" ;;
    launch_agent) printf '%s' "${LAUNCH_AGENT_PLIST}" ;;
    runtime_all) printf '%s' "${RUNTIME_DIR}" ;;
    logs) printf '%s' "${LOG_DIR}" ;;
    db) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/orquestra_v2.db" ;;
    memory) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/memorygraph" ;;
    rag_indexes) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/rag_runtime" ;;
    osint) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/osint" ;;
    workspace) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/workspace" ;;
    workflows) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/workflows" ;;
    operations) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/operations" ;;
    trainplane) printf '%s' "${RUNTIME_DIR}/experiments/orquestra/trainplane" ;;
    install_backups) printf '%s' "${INSTALL_BACKUP_DIR}" ;;
    runtime_venv) printf '%s' "${RUNTIME_DIR}/.venv" ;;
    *) printf '' ;;
  esac
}

item_label() {
  case "$1" in
    app) printf 'App instalado' ;;
    app_shortcut) printf 'Atalho Orquestra.app' ;;
    uninstaller_app) printf 'Orquestra Uninstaller.app' ;;
    launch_agent) printf 'LaunchAgent da API' ;;
    runtime_all) printf 'Runtime completo do Orquestra' ;;
    logs) printf 'Logs do usuario' ;;
    db) printf 'Banco local' ;;
    memory) printf 'MemoryGraph e memdir' ;;
    rag_indexes) printf 'Indices RAG/Chroma' ;;
    osint) printf 'Evidencias e investigacoes OSINT' ;;
    workspace) printf 'Workspace scans/extractions' ;;
    workflows) printf 'Workflow runs' ;;
    operations) printf 'Operations runs/artifacts' ;;
    trainplane) printf 'Train Plane local storage' ;;
    install_backups) printf 'Backups de instalacao' ;;
    runtime_venv) printf '.venv do runtime instalado' ;;
    brew_python) printf 'Homebrew python@3.12' ;;
    brew_node) printf 'Homebrew node' ;;
    brew_rust) printf 'Homebrew rust' ;;
    brew_uv) printf 'Homebrew uv' ;;
    brew_ffmpeg) printf 'Homebrew ffmpeg' ;;
    brew_tor) printf 'Homebrew tor' ;;
    brew_ollama) printf 'Homebrew ollama' ;;
    cask_brave) printf 'Cask Brave Browser' ;;
    cask_lmstudio) printf 'Cask LM Studio' ;;
    *) printf '%s' "$1" ;;
  esac
}

brew_bin() {
  if command -v brew >/dev/null 2>&1; then
    command -v brew
  elif [[ -x /opt/homebrew/bin/brew ]]; then
    printf '/opt/homebrew/bin/brew'
  elif [[ -x /usr/local/bin/brew ]]; then
    printf '/usr/local/bin/brew'
  else
    return 1
  fi
}

default_selection() {
  case "${MODE}" in
    preserve-deps)
      printf 'app,app_shortcut,uninstaller_app,launch_agent,runtime_all,logs'
      ;;
    safe)
      printf 'app,app_shortcut,uninstaller_app,launch_agent,runtime_all,logs'
      ;;
    all)
      printf 'app,app_shortcut,uninstaller_app,launch_agent,runtime_all,logs,db,memory,rag_indexes,osint,workspace,workflows,operations,trainplane,install_backups,runtime_venv,brew_python,brew_node,brew_rust,brew_uv,brew_ffmpeg,brew_tor,brew_ollama,cask_brave,cask_lmstudio'
      ;;
  esac
}

print_items() {
  cat <<'ITEMS'
Itens removiveis:
  app              App em ~/Applications
  app_shortcut     Atalho Orquestra.app em ~/Applications
  uninstaller_app  Orquestra Uninstaller.app em ~/Applications
  launch_agent     LaunchAgent ai.orquestra.api
  runtime_all      Runtime completo em Application Support
  logs             Logs do usuario
  db               Banco local
  memory           MemoryGraph e memdir
  rag_indexes      Indices RAG/Chroma
  osint            Evidencias e investigacoes OSINT
  workspace        Workspace scans/extractions
  workflows        Workflow runs
  operations       Operations runs/artifacts
  trainplane       Train Plane local storage
  install_backups  Backups de instalacao
  runtime_venv     .venv do runtime instalado

Dependencias globais, remova apenas se tiver certeza:
  brew_python,brew_node,brew_rust,brew_uv,brew_ffmpeg,brew_tor,brew_ollama
  cask_brave,cask_lmstudio
ITEMS
}

SELECTED="${SELECTED_RAW}"
if [[ -z "${SELECTED}" ]]; then
  SELECTED="$(default_selection)"
fi

if [[ -t 0 && "${DRY_RUN}" != "true" && -z "${SELECTED_RAW}" ]]; then
  print_items
  echo
  echo "[orquestra-full-uninstall] modo atual: ${MODE}"
  echo "[orquestra-full-uninstall] selecao padrao: ${SELECTED}"
  echo "Digite uma lista de ids separados por virgula para sobrescrever, ou Enter para manter."
  read -r custom_selection
  if [[ -n "${custom_selection}" ]]; then
    SELECTED="${custom_selection}"
  fi
fi

if [[ "${MODE}" == "safe" && ! "${SELECTED}" == *"brew_"* && ! "${SELECTED}" == *"cask_"* && -t 0 ]]; then
  if prompt_yes "Deseja incluir dependencias globais na remocao?"; then
    echo "Informe ids globais separados por virgula, por exemplo: brew_ffmpeg,brew_tor,cask_lmstudio"
    read -r global_selection
    if [[ -n "${global_selection}" ]]; then
      SELECTED="${SELECTED},${global_selection}"
    fi
  fi
fi

if [[ "${MODE}" == "all" && "${DRY_RUN}" != "true" && "${CONFIRM_REMOVE_ALL}" != "true" ]]; then
  if [[ -t 0 ]]; then
    echo "[orquestra-full-uninstall] ATENCAO: modo all pode remover dados, memorias e dependencias globais."
    echo "Digite REMOVER TUDO para continuar:"
    read -r confirmation
    if [[ "${confirmation}" != "REMOVER TUDO" ]]; then
      echo "[orquestra-full-uninstall] cancelado"
      exit 1
    fi
  else
    echo "[orquestra-full-uninstall] modo all exige --confirm-remove-all em execucao nao interativa" >&2
    exit 1
  fi
fi

has_sensitive_data_selection() {
  for item in db memory rag_indexes osint workspace workflows operations trainplane runtime_all; do
    if contains_item "${item}" "${SELECTED}"; then
      return 0
    fi
  done
  return 1
}

backup_sensitive_data() {
  if ! has_sensitive_data_selection; then
    return 0
  fi
  local should_backup="false"
  case "${BACKUP_MODE}" in
    yes) should_backup="true" ;;
    no) should_backup="false" ;;
    ask)
      if prompt_yes "Criar backup .tar.gz antes de remover dados/memorias?"; then
        should_backup="true"
      fi
      ;;
  esac
  if [[ "${should_backup}" != "true" ]]; then
    echo "[orquestra-full-uninstall] backup pulado"
    return 0
  fi
  local backup_root="${HOME}/Desktop"
  local backup_path="${backup_root}/orquestra-uninstall-backup-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
  local paths=()
  for item in db memory rag_indexes osint workspace workflows operations trainplane runtime_all; do
    if contains_item "${item}" "${SELECTED}"; then
      local path
      path="$(item_path "${item}")"
      if [[ -e "${path}" ]]; then
        paths+=("${path}")
      fi
    fi
  done
  if [[ "${#paths[@]}" -eq 0 ]]; then
    echo "[orquestra-full-uninstall] nenhum dado existente para backup"
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[orquestra-full-uninstall] dry-run backup: ${backup_path}"
    printf '  %s\n' "${paths[@]}"
    return 0
  fi
  tar -czf "${backup_path}" "${paths[@]}"
  echo "[orquestra-full-uninstall] backup criado: ${backup_path}"
}

remove_path() {
  local item="$1"
  local path
  path="$(item_path "${item}")"
  if [[ -z "${path}" ]]; then
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[orquestra-full-uninstall] dry-run remove $(item_label "${item}"): ${path}"
    return 0
  fi
  if [[ -e "${path}" ]]; then
    rm -rf "${path}"
    echo "[orquestra-full-uninstall] removido $(item_label "${item}"): ${path}"
  else
    echo "[orquestra-full-uninstall] ausente $(item_label "${item}"): ${path}"
  fi
}

remove_launch_agent() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[orquestra-full-uninstall] dry-run bootout/remove LaunchAgent: ${LAUNCH_AGENT_PLIST}"
    return 0
  fi
  launchctl bootout "gui/${UID}" "${LAUNCH_AGENT_PLIST}" >/dev/null 2>&1 || true
  rm -f "${LAUNCH_AGENT_PLIST}"
  echo "[orquestra-full-uninstall] LaunchAgent removido"
}

remove_app() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[orquestra-full-uninstall] dry-run pkill/remove app: ${INSTALL_DIR}"
    return 0
  fi
  pkill -x "${APP_PROCESS_NAME}" >/dev/null 2>&1 || true
  rm -rf "${INSTALL_DIR}"
  rm -rf "${APP_SHORTCUT_PATH}"
  rm -rf "${UNINSTALLER_INSTALL_DIR}"
  echo "[orquestra-full-uninstall] app removido: ${INSTALL_DIR}"
}

uninstall_brew_formula() {
  local item="$1"
  local formula="$2"
  if ! BREW_PATH="$(brew_bin 2>/dev/null)"; then
    echo "[orquestra-full-uninstall] Homebrew ausente; nao foi possivel remover ${formula}"
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[orquestra-full-uninstall] dry-run brew uninstall ${formula}"
    return 0
  fi
  "${BREW_PATH}" uninstall "${formula}" || true
  echo "[orquestra-full-uninstall] dependencia removida: $(item_label "${item}")"
}

uninstall_brew_cask() {
  local item="$1"
  local cask="$2"
  if ! BREW_PATH="$(brew_bin 2>/dev/null)"; then
    echo "[orquestra-full-uninstall] Homebrew ausente; nao foi possivel remover ${cask}"
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[orquestra-full-uninstall] dry-run brew uninstall --cask ${cask}"
    return 0
  fi
  "${BREW_PATH}" uninstall --cask "${cask}" || true
  echo "[orquestra-full-uninstall] cask removido: $(item_label "${item}")"
}

echo "[orquestra-full-uninstall] modo=${MODE} dry-run=${DRY_RUN}"
echo "[orquestra-full-uninstall] itens=${SELECTED}"

backup_sensitive_data

if contains_item "launch_agent" "${SELECTED}"; then remove_launch_agent; fi
if contains_item "app" "${SELECTED}"; then remove_app; fi
if contains_item "app_shortcut" "${SELECTED}" && ! contains_item "app" "${SELECTED}"; then remove_path "app_shortcut"; fi
if contains_item "uninstaller_app" "${SELECTED}" && ! contains_item "app" "${SELECTED}"; then remove_path "uninstaller_app"; fi

for item in runtime_all logs db memory rag_indexes osint workspace workflows operations trainplane install_backups runtime_venv; do
  if contains_item "${item}" "${SELECTED}"; then
    remove_path "${item}"
  fi
done

if contains_item "brew_python" "${SELECTED}"; then uninstall_brew_formula "brew_python" "python@3.12"; fi
if contains_item "brew_node" "${SELECTED}"; then uninstall_brew_formula "brew_node" "node"; fi
if contains_item "brew_rust" "${SELECTED}"; then uninstall_brew_formula "brew_rust" "rust"; fi
if contains_item "brew_uv" "${SELECTED}"; then uninstall_brew_formula "brew_uv" "uv"; fi
if contains_item "brew_ffmpeg" "${SELECTED}"; then uninstall_brew_formula "brew_ffmpeg" "ffmpeg"; fi
if contains_item "brew_tor" "${SELECTED}"; then uninstall_brew_formula "brew_tor" "tor"; fi
if contains_item "brew_ollama" "${SELECTED}"; then uninstall_brew_formula "brew_ollama" "ollama"; fi
if contains_item "cask_brave" "${SELECTED}"; then uninstall_brew_cask "cask_brave" "brave-browser"; fi
if contains_item "cask_lmstudio" "${SELECTED}"; then uninstall_brew_cask "cask_lmstudio" "lm-studio"; fi

echo "[orquestra-full-uninstall] concluido"
