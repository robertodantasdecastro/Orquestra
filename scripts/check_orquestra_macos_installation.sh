#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY="false"
STRICT="false"
MISSING_REQUIRED=0

usage() {
  cat <<'USAGE'
Uso: ./scripts/check_orquestra_macos_installation.sh [opcoes]

Opcoes:
  --check-only  Executa apenas verificacoes, sem modificar nada.
  --strict      Retorna erro se algum item obrigatorio estiver ausente.
  -h, --help    Mostra esta ajuda.

Categorias verificadas:
  sistema, build, app, runtime, providers, osint, multimodal e validacao.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      CHECK_ONLY="true"
      shift
      ;;
    --strict)
      STRICT="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[orquestra-check] argumento desconhecido: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

read_env_value() {
  local key="$1"
  local file="${ROOT_DIR}/.env"
  if [[ ! -f "${file}" ]]; then
    return 1
  fi
  grep -E "^${key}=" "${file}" | tail -n 1 | cut -d= -f2-
}

env_or_file() {
  local key="$1"
  local fallback="${2:-}"
  local current="${!key:-}"
  if [[ -n "${current}" ]]; then
    printf '%s' "${current}"
    return 0
  fi
  local from_file
  from_file="$(read_env_value "${key}" || true)"
  if [[ -n "${from_file}" ]]; then
    printf '%s' "${from_file}"
    return 0
  fi
  printf '%s' "${fallback}"
}

report() {
  local category="$1"
  local name="$2"
  local status="$3"
  local detail="$4"
  local fix="${5:-}"
  printf '[orquestra-check] category=%s item=%s status=%s detail=%s\n' "${category}" "${name}" "${status}" "${detail}"
  if [[ -n "${fix}" ]]; then
    printf '  fix: %s\n' "${fix}"
  fi
}

required_missing() {
  local category="$1"
  local name="$2"
  local detail="$3"
  local fix="$4"
  MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
  report "${category}" "${name}" "missing" "${detail}" "${fix}"
}

command_version() {
  local cmd="$1"
  shift || true
  if command -v "${cmd}" >/dev/null 2>&1; then
    "${cmd}" "$@" 2>&1 | head -n 1
  else
    printf 'ausente'
  fi
}

http_ready() {
  local url="$1"
  local code
  if code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 3 "${url}" 2>/dev/null)"; then
    [[ "${code}" =~ ^2|3|4 ]]
  else
    return 1
  fi
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

check_command_required() {
  local category="$1"
  local name="$2"
  local cmd="$3"
  local fix="$4"
  if command -v "${cmd}" >/dev/null 2>&1; then
    report "${category}" "${name}" "ok" "$(command_version "${cmd}" --version)"
  else
    required_missing "${category}" "${name}" "comando ${cmd} ausente" "${fix}"
  fi
}

check_command_optional() {
  local category="$1"
  local name="$2"
  local cmd="$3"
  local fix="$4"
  if command -v "${cmd}" >/dev/null 2>&1; then
    report "${category}" "${name}" "ok" "$(command -v "${cmd}")"
  else
    report "${category}" "${name}" "optional_missing" "comando ${cmd} ausente" "${fix}"
  fi
}

check_file() {
  local category="$1"
  local name="$2"
  local path="$3"
  local required="$4"
  local fix="$5"
  if [[ -e "${path}" ]]; then
    report "${category}" "${name}" "ok" "${path}"
  elif [[ "${required}" == "true" ]]; then
    required_missing "${category}" "${name}" "${path} ausente" "${fix}"
  else
    report "${category}" "${name}" "optional_missing" "${path} ausente" "${fix}"
  fi
}

echo "[orquestra-check] root=${ROOT_DIR}"
echo "[orquestra-check] modo check-only=${CHECK_ONLY}"

if [[ "$(uname -s)" == "Darwin" ]]; then
  report "sistema" "macos" "ok" "$(sw_vers -productVersion 2>/dev/null || uname -r)"
else
  required_missing "sistema" "macos" "este instalador e exclusivo para macOS" "usar um Mac para instalar o app desktop"
fi

report "sistema" "arquitetura" "ok" "$(uname -m)"

if xcode-select -p >/dev/null 2>&1; then
  report "sistema" "command_line_tools" "ok" "$(xcode-select -p)"
else
  required_missing "sistema" "command_line_tools" "Command Line Tools ausente" "xcode-select --install"
fi

if BREW_PATH="$(brew_bin 2>/dev/null)"; then
  report "sistema" "homebrew" "ok" "${BREW_PATH}"
else
  required_missing "sistema" "homebrew" "Homebrew ausente" "/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
fi

check_command_required "build" "python3.12" "python3.12" "brew install python@3.12"
check_command_required "build" "node" "node" "brew install node"
check_command_required "build" "npm" "npm" "brew install node"
check_command_required "build" "cargo" "cargo" "brew install rust"
check_command_required "build" "rustc" "rustc" "brew install rust"
check_command_required "build" "uv" "uv" "brew install uv"
check_command_required "build" "git" "git" "brew install git"

PACKAGE_VERSION="$(/usr/bin/python3 - <<'PY' "${ROOT_DIR}/orquestra_web/package.json"
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(str(payload.get("version", "0.2.0")))
PY
)"
APP_BUNDLE="${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app"
DMG_BUNDLE="${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_${PACKAGE_VERSION}_aarch64.dmg"
INSTALLED_APP="${HOME}/Applications/Orquestra AI.app"
SUPPORT_DIR="${HOME}/Library/Application Support/Orquestra"
RUNTIME_DIR="${SUPPORT_DIR}/runtime"
LOG_DIR="${HOME}/Library/Logs/Orquestra"
MANIFEST_PATH="${RUNTIME_DIR}/experiments/orquestra/install/install_manifest.json"
DB_PATH="${RUNTIME_DIR}/experiments/orquestra/orquestra_v2.db"
LAUNCH_AGENT_PLIST="${HOME}/Library/LaunchAgents/ai.orquestra.api.plist"

check_file "app" "venv" "${ROOT_DIR}/.venv" "true" "./scripts/bootstrap_orquestra.sh"
check_file "app" "node_modules" "${ROOT_DIR}/orquestra_web/node_modules" "true" "./scripts/bootstrap_orquestra.sh"
check_file "app" "bundle_app" "${APP_BUNDLE}" "false" "cd orquestra_web && npm run desktop:build"
check_file "app" "bundle_dmg" "${DMG_BUNDLE}" "false" "cd orquestra_web && npm run desktop:build"
check_file "app" "installed_app" "${INSTALLED_APP}" "false" "./scripts/install_orquestra_macos_full.sh"
check_file "app" "launch_agent" "${LAUNCH_AGENT_PLIST}" "false" "./scripts/install_orquestra_macos_full.sh"

check_file "runtime" "runtime_dir" "${RUNTIME_DIR}" "false" "./scripts/install_orquestra_macos_full.sh"
check_file "runtime" "logs_dir" "${LOG_DIR}" "false" "./scripts/install_orquestra_macos_full.sh"
check_file "runtime" "manifest" "${MANIFEST_PATH}" "false" "./scripts/install_orquestra_macos_full.sh"
check_file "runtime" "database" "${DB_PATH}" "false" "iniciar a API para criar o banco local"

API_URL="http://127.0.0.1:${ORQUESTRA_API_PORT:-8808}/api/health"
if http_ready "${API_URL}"; then
  report "runtime" "api" "online" "${API_URL}"
else
  report "runtime" "api" "offline" "${API_URL}" "./scripts/start_orquestra_api.sh"
fi

WEB_URL="http://127.0.0.1:4177"
if http_ready "${WEB_URL}"; then
  report "runtime" "web" "online" "${WEB_URL}"
else
  report "runtime" "web" "offline" "${WEB_URL}" "./scripts/start_orquestra_web.sh"
fi

LMSTUDIO_BASE="$(env_or_file LMSTUDIO_API_BASE "http://localhost:1234/v1")"
OLLAMA_BASE="$(env_or_file ORQUESTRA_OLLAMA_BASE_URL "http://localhost:11434")"
LITELLM_BASE="$(env_or_file ORQUESTRA_LITELLM_PROXY_URL "")"

if http_ready "${LMSTUDIO_BASE%/}/models"; then
  report "providers" "lmstudio" "online" "${LMSTUDIO_BASE%/}/models"
else
  report "providers" "lmstudio" "optional_offline" "${LMSTUDIO_BASE%/}/models" "abrir LM Studio e ativar Local Server"
fi

if http_ready "${OLLAMA_BASE%/}/api/tags"; then
  report "providers" "ollama" "online" "${OLLAMA_BASE%/}/api/tags"
else
  report "providers" "ollama" "optional_offline" "${OLLAMA_BASE%/}/api/tags" "brew install ollama"
fi

if [[ -n "${LITELLM_BASE}" ]] && http_ready "${LITELLM_BASE%/}/models"; then
  report "providers" "litellm_proxy" "online" "${LITELLM_BASE%/}/models"
elif [[ -n "${LITELLM_BASE}" ]]; then
  report "providers" "litellm_proxy" "offline" "${LITELLM_BASE%/}/models" "iniciar LiteLLM Proxy"
else
  report "providers" "litellm_proxy" "not_configured" "ORQUESTRA_LITELLM_PROXY_URL vazio"
fi

for key in OPENAI_API_KEY ANTHROPIC_API_KEY DEEPSEEK_API_KEY; do
  if [[ -n "$(env_or_file "${key}" "")" ]]; then
    report "providers" "${key}" "configured" "valor presente em ambiente ou .env"
  else
    report "providers" "${key}" "optional_missing" "chave ausente" "criar login/chave no provedor e preencher ${key} no .env"
  fi
done

for key in BRAVE_SEARCH_API_KEY TAVILY_API_KEY EXA_API_KEY YOUTUBE_API_KEY SHODAN_API_KEY CENSYS_API_ID CENSYS_API_SECRET REDDIT_CLIENT_ID REDDIT_CLIENT_SECRET; do
  if [[ -n "$(env_or_file "${key}" "")" ]]; then
    report "osint" "${key}" "configured" "valor presente em ambiente ou .env"
  else
    report "osint" "${key}" "optional_missing" "chave ausente" "preencher ${key} no .env se for usar esse conector"
  fi
done

TOR_PROXY="$(env_or_file ORQUESTRA_OSINT_TOR_PROXY_URL "socks5h://127.0.0.1:9050")"
TOR_HOST="$(printf '%s' "${TOR_PROXY}" | sed -E 's#^[a-zA-Z0-9+.-]+://([^:/]+):([0-9]+).*#\1#')"
TOR_PORT="$(printf '%s' "${TOR_PROXY}" | sed -E 's#^[a-zA-Z0-9+.-]+://([^:/]+):([0-9]+).*#\2#')"
if command -v nc >/dev/null 2>&1 && [[ -n "${TOR_HOST}" && -n "${TOR_PORT}" ]] && nc -z "${TOR_HOST}" "${TOR_PORT}" >/dev/null 2>&1; then
  report "osint" "tor_proxy" "online" "${TOR_PROXY}"
else
  report "osint" "tor_proxy" "optional_offline" "${TOR_PROXY}" "brew install tor && brew services start tor"
fi

check_command_optional "multimodal" "ffmpeg" "ffmpeg" "brew install ffmpeg"
check_command_optional "multimodal" "ffprobe" "ffprobe" "brew install ffmpeg"
check_command_optional "multimodal" "whisper" "whisper" "pipx install openai-whisper"

echo "[orquestra-check] validacao sugerida: ./scripts/validate_orquestra.sh"

if [[ "${STRICT}" == "true" && "${MISSING_REQUIRED}" -gt 0 ]]; then
  echo "[orquestra-check] modo estrito: ${MISSING_REQUIRED} item(ns) obrigatorio(s) ausente(s)" >&2
  exit 1
fi

echo "[orquestra-check] relatorio concluido"
