#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY="false"
ASSUME_YES="false"
REQUIRED_ONLY="false"
CONFIGURE_ENV="false"
SKIP_BUILD="false"
INSTALL_LAUNCH_AGENT="true"
SYNC_RUNTIME="true"
OPEN_APP="false"
RUN_VALIDATION="true"
OPTIONAL_LIST=""
JSON_MODE="false"
EMIT_EVENTS="false"
PLAN_FILE=""
OPTIONAL_WARNINGS=()

usage() {
  cat <<'USAGE'
Uso: ./scripts/install_orquestra_macos_full.sh [opcoes]

Instalador completo do Orquestra para macOS, incluindo verificacao/instalacao
de dependencias obrigatorias, orientacao de providers e chamada do instalador
base do app.

Opcoes:
  --check-only                     Apenas diagnostica; nao instala nada.
  --yes                            Assume sim para instalacoes CLI obrigatorias.
  --required-only                  Instala somente dependencias obrigatorias.
  --with-optional lista            Opcionais separados por virgula:
                                   brave,lmstudio,tor,ffmpeg,whisper,ollama
  --configure-env                  Guia preenchimento local do .env sem imprimir segredos.
  --skip-build                     Usa bundle existente.
  --no-launch-agent                Nao instala/inicia LaunchAgent.
  --no-runtime-sync                Nao sincroniza runtime instalado.
  --open                           Abre o app ao final.
  --skip-validation                Nao roda validate_orquestra.sh ao final.
  --json                           Emite contrato JSON machine-readable em modo check-only.
  --plan-file path                 Usa/salva plano JSON para UI grafica.
  --emit-events                    Emite eventos JSONL simples para UI grafica.
  --no-tty                         Alias seguro para execucao sem prompt interativo.
  --no-secrets-output              Garante que segredos nunca sejam impressos.
  -h, --help                       Mostra esta ajuda.

Exemplos:
  ./scripts/install_orquestra_macos_full.sh --check-only
  ./scripts/install_orquestra_macos_full.sh --yes --with-optional ffmpeg,tor
  ./scripts/install_orquestra_macos_full.sh --required-only --configure-env
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      CHECK_ONLY="true"
      shift
      ;;
    --yes)
      ASSUME_YES="true"
      shift
      ;;
    --required-only)
      REQUIRED_ONLY="true"
      shift
      ;;
    --with-optional)
      OPTIONAL_LIST="${2:-}"
      if [[ -z "${OPTIONAL_LIST}" ]]; then
        echo "[orquestra-full-install] --with-optional exige uma lista" >&2
        exit 2
      fi
      shift 2
      ;;
    --configure-env)
      CONFIGURE_ENV="true"
      shift
      ;;
    --skip-build)
      SKIP_BUILD="true"
      shift
      ;;
    --no-launch-agent)
      INSTALL_LAUNCH_AGENT="false"
      shift
      ;;
    --no-runtime-sync)
      SYNC_RUNTIME="false"
      shift
      ;;
    --open)
      OPEN_APP="true"
      shift
      ;;
    --skip-validation)
      RUN_VALIDATION="false"
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
      echo "[orquestra-full-install] argumento desconhecido: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${JSON_MODE}" == "true" && "${CHECK_ONLY}" == "true" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" install-plan
  exit 0
fi

if [[ -n "${PLAN_FILE}" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" install-plan > "${PLAN_FILE}"
fi

if [[ "${EMIT_EVENTS}" == "true" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" emit-smoke
fi

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

ensure_homebrew() {
  if BREW_PATH="$(brew_bin 2>/dev/null)"; then
    echo "[orquestra-full-install] Homebrew: ${BREW_PATH}"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    echo "[orquestra-full-install] Homebrew ausente"
    return 0
  fi
  if prompt_yes "Homebrew ausente. Instalar agora?"; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null || true)"
  else
    echo "[orquestra-full-install] Homebrew e obrigatorio para instalacao automatizada" >&2
    exit 1
  fi
}

ensure_command_with_brew() {
  local label="$1"
  local command_name="$2"
  local formula="$3"
  if command -v "${command_name}" >/dev/null 2>&1; then
    echo "[orquestra-full-install] ok: ${label} ($(command -v "${command_name}"))"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    echo "[orquestra-full-install] missing: ${label}; fix: brew install ${formula}"
    return 0
  fi
  if prompt_yes "${label} ausente. Instalar '${formula}' via Homebrew?"; then
    "$(brew_bin)" install "${formula}"
  else
    echo "[orquestra-full-install] dependencia obrigatoria ausente: ${label}" >&2
    exit 1
  fi
}

install_formula_optional() {
  local formula="$1"
  local command_name="$2"
  if command -v "${command_name}" >/dev/null 2>&1; then
    echo "[orquestra-full-install] opcional ja instalado: ${formula}"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    echo "[orquestra-full-install] optional_missing: ${formula}; fix: brew install ${formula}"
    return 0
  fi
  if ! "$(brew_bin)" install "${formula}"; then
    OPTIONAL_WARNINGS+=("${formula}: falha ao instalar via Homebrew; seguindo sem bloquear o núcleo do Orquestra.")
    echo "[orquestra-full-install] aviso opcional: ${formula} falhou; seguindo sem bloquear a instalacao"
  fi
}

cask_known_app_path() {
  local cask="$1"
  case "${cask}" in
    lm-studio)
      if [[ -d "/Applications/LM Studio.app" ]]; then
        printf '/Applications/LM Studio.app'
        return 0
      fi
      if [[ -d "${HOME}/Applications/LM Studio.app" ]]; then
        printf '%s/Applications/LM Studio.app' "${HOME}"
        return 0
      fi
      ;;
    brave-browser)
      if [[ -d "/Applications/Brave Browser.app" ]]; then
        printf '/Applications/Brave Browser.app'
        return 0
      fi
      if [[ -d "${HOME}/Applications/Brave Browser.app" ]]; then
        printf '%s/Applications/Brave Browser.app' "${HOME}"
        return 0
      fi
      ;;
  esac
  return 1
}

install_cask_optional() {
  local cask="$1"
  local existing_app=""
  if "$(brew_bin)" list --cask "${cask}" >/dev/null 2>&1; then
    echo "[orquestra-full-install] opcional ja instalado via Homebrew: ${cask}"
    return 0
  fi
  existing_app="$(cask_known_app_path "${cask}" || true)"
  if [[ -n "${existing_app}" ]]; then
    echo "[orquestra-full-install] opcional ja disponivel: ${cask} (${existing_app})"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    echo "[orquestra-full-install] optional cask: ${cask}; fix: brew install --cask ${cask}"
    return 0
  fi
  if ! "$(brew_bin)" install --cask "${cask}"; then
    OPTIONAL_WARNINGS+=("${cask}: falha ao instalar o app opcional; verifique se já existe uma cópia em /Applications.")
    echo "[orquestra-full-install] aviso opcional: ${cask} falhou; seguindo sem bloquear a instalacao"
  fi
}

optional_selected() {
  local target="$1"
  if [[ "${REQUIRED_ONLY}" == "true" ]]; then
    return 1
  fi
  local normalized
  normalized=",${OPTIONAL_LIST// /},"
  [[ "${normalized}" == *",${target},"* ]]
}

ensure_xcode_tools() {
  if xcode-select -p >/dev/null 2>&1; then
    echo "[orquestra-full-install] Command Line Tools: $(xcode-select -p)"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    echo "[orquestra-full-install] missing: Command Line Tools; fix: xcode-select --install"
    return 0
  fi
  echo "[orquestra-full-install] Command Line Tools ausente."
  echo "[orquestra-full-install] O macOS abrira o instalador da Apple; execute novamente este script apos concluir."
  xcode-select --install || true
  exit 1
}

ensure_env_file() {
  if [[ -f "${ROOT_DIR}/.env" ]]; then
    chmod 600 "${ROOT_DIR}/.env" || true
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    echo "[orquestra-full-install] .env ausente; sera criado a partir de .env.example"
    return 0
  fi
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  chmod 600 "${ROOT_DIR}/.env" || true
  echo "[orquestra-full-install] .env criado com permissao restrita"
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  local file="${ROOT_DIR}/.env"
  if [[ ! -f "${file}" ]]; then
    cp "${ROOT_DIR}/.env.example" "${file}"
  fi
  chmod 600 "${file}" || true
  if grep -qE "^${key}=" "${file}"; then
    local tmp
    tmp="$(mktemp)"
    awk -v key="${key}" -v value="${value}" 'BEGIN{done=0} $0 ~ "^" key "=" {print key "=" value; done=1; next} {print} END{if(!done) print key "=" value}' "${file}" > "${tmp}"
    mv "${tmp}" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

prompt_env_secret() {
  local key="$1"
  local label="$2"
  local url="$3"
  if [[ "${CONFIGURE_ENV}" != "true" || "${CHECK_ONLY}" == "true" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    echo "[orquestra-full-install] configure ${key} manualmente no .env (${url})"
    return 0
  fi
  echo
  echo "[orquestra-full-install] ${label}"
  echo "  guia: ${url}"
  echo "  deixe em branco para pular"
  local value
  printf '  %s: ' "${key}"
  read -r -s value
  printf '\n'
  if [[ -n "${value}" ]]; then
    upsert_env_value "${key}" "${value}"
    echo "  ${key}: salvo no .env local"
  fi
}

guide_configuration() {
  cat <<'GUIDE'

[orquestra-full-install] Guia rapido de contas/chaves opcionais
  LM Studio: instalar app, baixar modelo e ativar Local Server em http://localhost:1234/v1
  OpenAI: criar conta/chave em https://platform.openai.com/api-keys
  Anthropic: criar conta/chave em https://console.anthropic.com/settings/keys
  DeepSeek: criar conta/chave em https://platform.deepseek.com/api_keys
  Brave Search API: criar chave em https://api.search.brave.com/
  Tavily: criar chave em https://app.tavily.com/
  Exa: criar chave em https://dashboard.exa.ai/api-keys
  YouTube Data API: criar projeto/chave no Google Cloud Console
  Shodan: criar chave em https://account.shodan.io/
  Censys: criar API ID/Secret em https://search.censys.io/account/api
  Tor proxy local: brew install tor && brew services start tor

O instalador nunca versiona chaves e nao imprime segredos.
GUIDE
}

configure_env_if_requested() {
  ensure_env_file
  if [[ "${CONFIGURE_ENV}" != "true" ]]; then
    return 0
  fi
  upsert_env_value "LMSTUDIO_API_BASE" "http://localhost:1234/v1"
  upsert_env_value "ORQUESTRA_OSINT_TOR_PROXY_URL" "socks5h://127.0.0.1:9050"
  prompt_env_secret "OPENAI_API_KEY" "OpenAI API key" "https://platform.openai.com/api-keys"
  prompt_env_secret "ANTHROPIC_API_KEY" "Anthropic API key" "https://console.anthropic.com/settings/keys"
  prompt_env_secret "DEEPSEEK_API_KEY" "DeepSeek API key" "https://platform.deepseek.com/api_keys"
  prompt_env_secret "BRAVE_SEARCH_API_KEY" "Brave Search API key" "https://api.search.brave.com/"
  prompt_env_secret "TAVILY_API_KEY" "Tavily API key" "https://app.tavily.com/"
  prompt_env_secret "EXA_API_KEY" "Exa API key" "https://dashboard.exa.ai/api-keys"
  prompt_env_secret "YOUTUBE_API_KEY" "YouTube Data API key" "https://console.cloud.google.com/apis/credentials"
  prompt_env_secret "SHODAN_API_KEY" "Shodan API key" "https://account.shodan.io/"
  prompt_env_secret "CENSYS_API_ID" "Censys API ID" "https://search.censys.io/account/api"
  prompt_env_secret "CENSYS_API_SECRET" "Censys API Secret" "https://search.censys.io/account/api"
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-full-install] este instalador e apenas para macOS" >&2
  exit 1
fi

echo "[orquestra-full-install] root: ${ROOT_DIR}"
echo "[orquestra-full-install] modo check-only=${CHECK_ONLY}"

ensure_xcode_tools
ensure_homebrew
ensure_command_with_brew "Python 3.12" "python3.12" "python@3.12"
ensure_command_with_brew "Node.js" "node" "node"
ensure_command_with_brew "npm" "npm" "node"
ensure_command_with_brew "Cargo" "cargo" "rust"
ensure_command_with_brew "Rust compiler" "rustc" "rust"
ensure_command_with_brew "uv" "uv" "uv"
ensure_command_with_brew "git" "git" "git"

if optional_selected "ffmpeg"; then
  install_formula_optional "ffmpeg" "ffmpeg"
fi
if optional_selected "tor"; then
  install_formula_optional "tor" "tor"
  if [[ "${CHECK_ONLY}" != "true" ]]; then
    if ! "$(brew_bin)" services start tor; then
      OPTIONAL_WARNINGS+=("tor: serviço local não iniciou automaticamente; inicie manualmente se quiser usar fetch via Tor.")
      echo "[orquestra-full-install] aviso opcional: nao foi possivel iniciar o servico do Tor automaticamente"
    fi
  fi
fi
if optional_selected "ollama"; then
  install_formula_optional "ollama" "ollama"
fi
if optional_selected "brave"; then
  install_cask_optional "brave-browser"
fi
if optional_selected "lmstudio"; then
  install_cask_optional "lm-studio"
fi
if optional_selected "whisper"; then
  install_formula_optional "pipx" "pipx"
  if [[ "${CHECK_ONLY}" != "true" ]]; then
    if ! command -v whisper >/dev/null 2>&1 && [[ ! -x "${HOME}/.local/bin/whisper" && ! -x "${HOME}/Library/Python/3.12/bin/whisper" ]]; then
      pipx install openai-whisper
      pipx ensurepath || true
    fi
  fi
fi

guide_configuration
configure_env_if_requested

if [[ "${CHECK_ONLY}" == "true" ]]; then
  "${ROOT_DIR}/scripts/check_orquestra_macos_installation.sh" --check-only
  echo "[orquestra-full-install] check-only concluido"
  exit 0
fi

echo "[orquestra-full-install] preparando dependencias do projeto"
"${ROOT_DIR}/scripts/bootstrap_orquestra.sh"

if [[ "${SKIP_BUILD}" != "true" ]]; then
  echo "[orquestra-full-install] gerando app desktop"
  (
    cd "${ROOT_DIR}/orquestra_web"
    npm run desktop:build
  )
else
  echo "[orquestra-full-install] build pulado (--skip-build)"
fi

BASE_INSTALL_ARGS=(--skip-build)
if [[ "${INSTALL_LAUNCH_AGENT}" != "true" ]]; then
  BASE_INSTALL_ARGS+=(--no-launch-agent)
fi
if [[ "${SYNC_RUNTIME}" != "true" ]]; then
  BASE_INSTALL_ARGS+=(--no-runtime-sync)
fi
if [[ "${OPEN_APP}" == "true" ]]; then
  BASE_INSTALL_ARGS+=(--open)
fi

echo "[orquestra-full-install] instalando app e runtime"
"${ROOT_DIR}/scripts/install_orquestra_macos.sh" "${BASE_INSTALL_ARGS[@]}"

echo "[orquestra-full-install] verificando instalacao"
"${ROOT_DIR}/scripts/check_orquestra_macos_installation.sh" --check-only

if [[ "${RUN_VALIDATION}" == "true" ]]; then
  echo "[orquestra-full-install] executando validacao oficial"
  "${ROOT_DIR}/scripts/validate_orquestra.sh"
else
  echo "[orquestra-full-install] validacao oficial pulada (--skip-validation)"
fi

echo
echo "[orquestra-full-install] instalacao completa concluida"
echo "  app: ${HOME}/Applications/Orquestra AI.app"
echo "  runtime: ${HOME}/Library/Application Support/Orquestra/runtime"
echo "  logs: ${HOME}/Library/Logs/Orquestra"
if [[ ${#OPTIONAL_WARNINGS[@]} -gt 0 ]]; then
  echo
  echo "[orquestra-full-install] avisos opcionais:"
  for warning in "${OPTIONAL_WARNINGS[@]}"; do
    echo "  - ${warning}"
  done
fi
