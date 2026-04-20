#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STRICT=0
REQUIRED_PROVIDERS=()

usage() {
  cat <<'EOF'
Uso: ./scripts/check_orquestra_providers.sh [--strict] [--require provider]

Opções:
  --strict            Falha se um provider requerido não estiver pronto/configurado.
  --require provider  Exige um provider específico. Pode ser repetido.
  -h, --help          Mostra esta ajuda.

Providers reconhecidos:
  lmstudio
  ollama
  litellm_proxy
  openai
  anthropic
  deepseek
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=1
      shift
      ;;
    --require)
      if [[ $# -lt 2 ]]; then
        echo "[orquestra-providers] --require precisa de um provider" >&2
        exit 1
      fi
      REQUIRED_PROVIDERS+=("$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[orquestra-providers] argumento desconhecido: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

read_env_value() {
  local key="$1"
  local file="${2:-.env}"
  if [[ ! -f "$file" ]]; then
    return 1
  fi
  grep -E "^${key}=" "$file" | tail -n 1 | cut -d= -f2-
}

env_or_file() {
  local key="$1"
  local fallback="${2:-}"
  local current="${!key:-}"
  if [[ -n "$current" ]]; then
    printf '%s' "$current"
    return 0
  fi
  local from_file
  from_file="$(read_env_value "$key" .env || true)"
  if [[ -n "$from_file" ]]; then
    printf '%s' "$from_file"
    return 0
  fi
  printf '%s' "$fallback"
}

if [[ -f .env ]]; then
  echo "[orquestra-providers] .env detectado; lendo apenas variáveis relevantes"
else
  echo "[orquestra-providers] .env ausente; usando apenas variáveis do ambiente"
fi

http_ready() {
  local url="$1"
  local code
  if code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null)"; then
    [[ "$code" =~ ^2|3|4 ]]
  else
    return 1
  fi
}

is_required() {
  local target="$1"
  if [[ ${#REQUIRED_PROVIDERS[@]} -eq 0 ]]; then
    return 0
  fi
  local item
  for item in "${REQUIRED_PROVIDERS[@]}"; do
    if [[ "$item" == "$target" ]]; then
      return 0
    fi
  done
  return 1
}

report() {
  local provider="$1"
  local status="$2"
  local detail="$3"
  printf '[orquestra-providers] provider=%s status=%s detail=%s\n' "$provider" "$status" "$detail"
}

check_result=0

ensure_ok_when_required() {
  local provider="$1"
  local status="$2"
  if [[ "$STRICT" -ne 1 ]]; then
    return 0
  fi
  if ! is_required "$provider"; then
    return 0
  fi
  case "$status" in
    online|configured)
      return 0
      ;;
    *)
      check_result=1
      return 0
      ;;
  esac
}

LMSTUDIO_BASE="$(env_or_file LMSTUDIO_API_BASE "http://localhost:1234/v1")"
OLLAMA_BASE="$(env_or_file ORQUESTRA_OLLAMA_BASE_URL "http://localhost:11434")"
LITELLM_BASE="$(env_or_file ORQUESTRA_LITELLM_PROXY_URL "")"

if http_ready "${LMSTUDIO_BASE%/}/models"; then
  report "lmstudio" "online" "${LMSTUDIO_BASE%/}/models"
  ensure_ok_when_required "lmstudio" "online"
else
  report "lmstudio" "offline" "${LMSTUDIO_BASE%/}/models"
  ensure_ok_when_required "lmstudio" "offline"
fi

if http_ready "${OLLAMA_BASE%/}/api/tags"; then
  report "ollama" "online" "${OLLAMA_BASE%/}/api/tags"
  ensure_ok_when_required "ollama" "online"
else
  report "ollama" "offline" "${OLLAMA_BASE%/}/api/tags"
  ensure_ok_when_required "ollama" "offline"
fi

if [[ -n "${LITELLM_BASE}" ]]; then
  if http_ready "${LITELLM_BASE%/}/models"; then
    report "litellm_proxy" "online" "${LITELLM_BASE%/}/models"
    ensure_ok_when_required "litellm_proxy" "online"
  else
    report "litellm_proxy" "offline" "${LITELLM_BASE%/}/models"
    ensure_ok_when_required "litellm_proxy" "offline"
  fi
else
  report "litellm_proxy" "not_configured" "ORQUESTRA_LITELLM_PROXY_URL vazio"
  ensure_ok_when_required "litellm_proxy" "not_configured"
fi

if [[ -n "$(env_or_file OPENAI_API_KEY "")" ]]; then
  report "openai" "configured" "OPENAI_API_KEY presente"
  ensure_ok_when_required "openai" "configured"
else
  report "openai" "missing_key" "OPENAI_API_KEY ausente"
  ensure_ok_when_required "openai" "missing_key"
fi

if [[ -n "$(env_or_file ANTHROPIC_API_KEY "")" ]]; then
  report "anthropic" "configured" "ANTHROPIC_API_KEY presente"
  ensure_ok_when_required "anthropic" "configured"
else
  report "anthropic" "missing_key" "ANTHROPIC_API_KEY ausente"
  ensure_ok_when_required "anthropic" "missing_key"
fi

if [[ -n "$(env_or_file DEEPSEEK_API_KEY "")" ]]; then
  report "deepseek" "configured" "DEEPSEEK_API_KEY presente"
  ensure_ok_when_required "deepseek" "configured"
else
  report "deepseek" "missing_key" "DEEPSEEK_API_KEY ausente"
  ensure_ok_when_required "deepseek" "missing_key"
fi

if [[ "$STRICT" -eq 1 ]]; then
  if [[ "$check_result" -eq 0 ]]; then
    echo "[orquestra-providers] modo estrito: todos os providers requeridos estão prontos/configurados"
  else
    echo "[orquestra-providers] modo estrito: há providers requeridos sem prontidão" >&2
  fi
else
  echo "[orquestra-providers] relatório concluído"
fi

exit "$check_result"
