#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-install] este instalador é apenas para macOS" >&2
  exit 1
fi

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_NAME="Orquestra AI.app"
APP_SHORTCUT_NAME="Orquestra.app"
UNINSTALLER_NAME="Orquestra Uninstaller.app"
INSTALL_DIR="${ORQUESTRA_INSTALL_DIR:-$HOME/Applications/$APP_NAME}"
APP_SHORTCUT_PATH="${ORQUESTRA_APP_SHORTCUT_PATH:-$HOME/Applications/$APP_SHORTCUT_NAME}"
UNINSTALLER_INSTALL_DIR="${ORQUESTRA_UNINSTALLER_INSTALL_DIR:-$HOME/Applications/$UNINSTALLER_NAME}"
APP_SOURCE="${ORQUESTRA_APP_SOURCE:-${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/macos/${APP_NAME}}"
UNINSTALLER_SOURCE="${ORQUESTRA_UNINSTALLER_SOURCE:-${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/macos/${UNINSTALLER_NAME}}"
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
DMG_PATH="${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_${PACKAGE_VERSION}_aarch64.dmg"
SUPPORT_DIR="${HOME}/Library/Application Support/Orquestra"
RUNTIME_DIR="${SUPPORT_DIR}/runtime"
INSTALL_STATE_DIR="${RUNTIME_DIR}/experiments/orquestra/install"
BACKUP_DIR="${INSTALL_STATE_DIR}/backups"
MANIFEST_PATH="${INSTALL_STATE_DIR}/install_manifest.json"
RUNTIME_CONFIG_PATH="${RUNTIME_DIR}/config/runtime.json"
DB_PATH="${RUNTIME_DIR}/experiments/orquestra/orquestra_v2.db"
LOG_DIR="${HOME}/Library/Logs/Orquestra"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LAUNCH_AGENT_LABEL="ai.orquestra.api"
LAUNCH_AGENT_PLIST="${LAUNCH_AGENTS_DIR}/${LAUNCH_AGENT_LABEL}.plist"
API_URL="http://127.0.0.1:${ORQUESTRA_API_PORT:-8808}/api/health"
SKIP_BUILD="false"
INSTALL_LAUNCH_AGENT="true"
VERIFY_PACKAGE="true"
WAIT_API="true"
OPEN_APP="false"
SYNC_RUNTIME="true"
JSON_MODE="false"
PLAN_FILE=""

usage() {
  cat <<USAGE
Uso: ./scripts/install_orquestra_macos.sh [opcoes]

Opcoes:
  --skip-build         Usa o bundle Tauri ja existente em vez de recompilar.
  --skip-package-verify
                       Pula a validação local de .app, DMG, plist e scripts.
  --no-launch-agent   Instala apenas o app em ~/Applications, sem iniciar a API.
  --no-runtime-sync   Não espelha o runtime em ~/Library/Application Support/Orquestra/runtime.
  --no-wait-api       Não aguarda /api/health após registrar o LaunchAgent.
  --open              Abre o app instalado ao final.
  --json             Emite plano JSON machine-readable e sai.
  --plan-file PATH   Salva plano JSON para UI grafica.
  --install-dir PATH  Define o destino do .app. Padrao: ~/Applications/Orquestra AI.app.
  -h, --help          Mostra esta ajuda.

Variaveis uteis:
  ORQUESTRA_ROOT          Raiz do repositorio.
  ORQUESTRA_INSTALL_DIR   Destino do app.
  ORQUESTRA_API_PORT      Porta da API local. Padrao: 8808.
  ORQUESTRA_INSTALL_API_WAIT_SECONDS
                         Tempo maximo para aguardar /api/health. Padrao: 90.
  ORQUESTRA_INSTALL_BACKUP_LIMIT
                         Quantos backups de banco manter. Padrao: 5.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build)
      SKIP_BUILD="true"
      shift
      ;;
    --no-launch-agent)
      INSTALL_LAUNCH_AGENT="false"
      shift
      ;;
    --skip-package-verify)
      VERIFY_PACKAGE="false"
      shift
      ;;
    --no-runtime-sync)
      SYNC_RUNTIME="false"
      shift
      ;;
    --no-wait-api)
      WAIT_API="false"
      shift
      ;;
    --open)
      OPEN_APP="true"
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
    --install-dir)
      INSTALL_DIR="${2:-}"
      if [[ -z "${INSTALL_DIR}" ]]; then
        echo "[orquestra-install] --install-dir exige um caminho" >&2
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[orquestra-install] opcao invalida: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ "${JSON_MODE}" == "true" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" install-plan
  exit 0
fi

if [[ -n "${PLAN_FILE}" ]]; then
  /usr/bin/python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" install-plan > "${PLAN_FILE}"
fi

mkdir -p "$(dirname "${INSTALL_DIR}")" "${SUPPORT_DIR}" "${LOG_DIR}" "${LAUNCH_AGENTS_DIR}"

create_launcher_app() {
  local launcher_app="$1"
  local target_app="$2"
  local icon_source="$3"
  local launcher_exec="orquestra-launcher"
  local launcher_id="com.localrag.orquestra.launcher"
  local quoted_target

  quoted_target="$(/usr/bin/python3 - <<'PY' "${target_app}"
import shlex
import sys

print(shlex.quote(sys.argv[1]))
PY
)"

  rm -rf "${launcher_app}"
  mkdir -p "${launcher_app}/Contents/MacOS" "${launcher_app}/Contents/Resources"

  if [[ -f "${icon_source}" ]]; then
    cp "${icon_source}" "${launcher_app}/Contents/Resources/icon.icns"
  fi

  cat > "${launcher_app}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>English</string>
  <key>CFBundleDisplayName</key>
  <string>Orquestra</string>
  <key>CFBundleExecutable</key>
  <string>${launcher_exec}</string>
  <key>CFBundleIconFile</key>
  <string>icon.icns</string>
  <key>CFBundleIdentifier</key>
  <string>${launcher_id}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Orquestra</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${PACKAGE_VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${PACKAGE_VERSION}</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.13</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

  cat > "${launcher_app}/Contents/MacOS/${launcher_exec}" <<SH
#!/usr/bin/env bash
set -euo pipefail

TARGET_APP=${quoted_target}

if [[ ! -d "\${TARGET_APP}" ]]; then
  /usr/bin/osascript -e 'display dialog "O Orquestra AI.app nao foi encontrado no local esperado. Reinstale o Orquestra para recriar o launcher." buttons {"OK"} default button "OK" with title "Orquestra"'
  exit 1
fi

exec /usr/bin/open "\${TARGET_APP}"
SH
  chmod +x "${launcher_app}/Contents/MacOS/${launcher_exec}"
}

echo "[orquestra-install] root: ${ROOT_DIR}"
if [[ "${SKIP_BUILD}" != "true" ]]; then
  echo "[orquestra-install] preparando ambiente local"
  "${ROOT_DIR}/scripts/bootstrap_orquestra.sh"

  echo "[orquestra-install] gerando app desktop"
  (
    cd "${ROOT_DIR}/orquestra_web"
    npm run desktop:build
    npm run desktop:build:uninstaller
  )
else
  echo "[orquestra-install] usando bundle existente (--skip-build)"
fi

if [[ ! -d "${APP_SOURCE}" ]]; then
  echo "[orquestra-install] app bundle ausente: ${APP_SOURCE}" >&2
  exit 1
fi

if [[ ! -d "${UNINSTALLER_SOURCE}" ]]; then
  echo "[orquestra-install] desinstalador gráfico ausente: ${UNINSTALLER_SOURCE}" >&2
  exit 1
fi

if [[ "${VERIFY_PACKAGE}" == "true" ]]; then
  echo "[orquestra-install] validando pacote macOS"
  "${ROOT_DIR}/scripts/validate_orquestra_macos_package.sh"
fi

echo "[orquestra-install] instalando app em ${INSTALL_DIR}"
rm -rf "${INSTALL_DIR}"
ditto "${APP_SOURCE}" "${INSTALL_DIR}"

echo "[orquestra-install] instalando desinstalador em ${UNINSTALLER_INSTALL_DIR}"
rm -rf "${UNINSTALLER_INSTALL_DIR}"
ditto "${UNINSTALLER_SOURCE}" "${UNINSTALLER_INSTALL_DIR}"

echo "[orquestra-install] criando launcher de abertura em ${APP_SHORTCUT_PATH}"
create_launcher_app "${APP_SHORTCUT_PATH}" "${INSTALL_DIR}" "${INSTALL_DIR}/Contents/Resources/icon.icns"

if [[ "${INSTALL_LAUNCH_AGENT}" != "true" ]]; then
  echo
  echo "[orquestra-install] instalação concluída sem LaunchAgent"
  echo "  app: ${INSTALL_DIR}"
  echo "  atalho app: ${APP_SHORTCUT_PATH}"
  echo "  desinstalador: ${UNINSTALLER_INSTALL_DIR}"
  echo "  dados: ${SUPPORT_DIR}"
  echo "  logs: ${LOG_DIR}"
  if [[ "${OPEN_APP}" == "true" ]]; then
    /usr/bin/open -n "${INSTALL_DIR}"
  fi
  exit 0
fi

if [[ "${SYNC_RUNTIME}" == "true" ]]; then
  if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
    echo "[orquestra-install] .venv ausente; preparando dependências antes do runtime"
    "${ROOT_DIR}/scripts/bootstrap_orquestra.sh"
  fi

  PREVIOUS_VERSION=""
  PREVIOUS_INSTALLED_AT=""
  if [[ -f "${MANIFEST_PATH}" ]]; then
    PREVIOUS_VERSION="$(/usr/bin/python3 - <<'PY' "${MANIFEST_PATH}"
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(str(payload.get("app_version", "")))
PY
)"
    PREVIOUS_INSTALLED_AT="$(/usr/bin/python3 - <<'PY' "${MANIFEST_PATH}"
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(str(payload.get("installed_at", "")))
PY
)"
  fi

  BACKUP_PATH=""
  BACKUP_CREATED="false"
  mkdir -p "${BACKUP_DIR}"
  if [[ -f "${DB_PATH}" ]]; then
    BACKUP_PATH="${BACKUP_DIR}/orquestra_v2-$(date -u +%Y%m%dT%H%M%SZ).db"
    cp "${DB_PATH}" "${BACKUP_PATH}"
    BACKUP_CREATED="true"
    echo "[orquestra-install] backup do banco salvo em ${BACKUP_PATH}"

    BACKUP_LIMIT="${ORQUESTRA_INSTALL_BACKUP_LIMIT:-5}"
    EXISTING_BACKUPS=()
    while IFS= read -r BACKUP_ITEM; do
      EXISTING_BACKUPS+=("${BACKUP_ITEM}")
    done < <(ls -1t "${BACKUP_DIR}"/orquestra_v2-*.db 2>/dev/null || true)
    if [[ "${#EXISTING_BACKUPS[@]}" -gt "${BACKUP_LIMIT}" ]]; then
      for OLD_BACKUP in "${EXISTING_BACKUPS[@]:${BACKUP_LIMIT}}"; do
        rm -f "${OLD_BACKUP}"
      done
    fi
  fi

  echo "[orquestra-install] sincronizando runtime local em ${RUNTIME_DIR}"
  mkdir -p "${RUNTIME_DIR}"
  rsync -a --delete "${ROOT_DIR}/orquestra_ai" "${RUNTIME_DIR}/"
  rsync -a --delete "${ROOT_DIR}/rag" "${RUNTIME_DIR}/"
  rsync -a --delete "${ROOT_DIR}/training" "${RUNTIME_DIR}/"
  rsync -a --delete "${ROOT_DIR}/scripts" "${RUNTIME_DIR}/"
  rsync -a --delete "${ROOT_DIR}/assets" "${RUNTIME_DIR}/"
  rsync -a --delete "${ROOT_DIR}/docs" "${RUNTIME_DIR}/"
  rsync -a --delete --exclude "node_modules" --exclude "src-tauri/target" "${ROOT_DIR}/orquestra_web" "${RUNTIME_DIR}/"
  rsync -a --delete "${ROOT_DIR}/.venv" "${RUNTIME_DIR}/"
  rsync -a "${ROOT_DIR}/requirements-orquestra.txt" "${RUNTIME_DIR}/requirements-orquestra.txt"
  rsync -a "${ROOT_DIR}/.env.example" "${RUNTIME_DIR}/.env.example"
  if [[ -f "${ROOT_DIR}/.env" ]]; then
    rsync -a "${ROOT_DIR}/.env" "${RUNTIME_DIR}/.env"
  fi

  export ORQUESTRA_INSTALL_MANIFEST_PATH="${MANIFEST_PATH}"
  export ORQUESTRA_INSTALL_APP_NAME="Orquestra AI"
  export ORQUESTRA_INSTALL_APP_VERSION="${PACKAGE_VERSION}"
  export ORQUESTRA_INSTALL_SOURCE_ROOT="${ROOT_DIR}"
  export ORQUESTRA_INSTALL_TARGET_APP="${INSTALL_DIR}"
  export ORQUESTRA_INSTALL_APP_SHORTCUT="${APP_SHORTCUT_PATH}"
  export ORQUESTRA_INSTALL_UNINSTALLER_APP="${UNINSTALLER_INSTALL_DIR}"
  export ORQUESTRA_INSTALL_RUNTIME_DIR="${RUNTIME_DIR}"
  export ORQUESTRA_INSTALL_SUPPORT_DIR="${SUPPORT_DIR}"
  export ORQUESTRA_INSTALL_LOG_DIR="${LOG_DIR}"
  export ORQUESTRA_INSTALL_API_URL="${API_URL}"
  export ORQUESTRA_INSTALL_LAUNCH_AGENT="${LAUNCH_AGENT_LABEL}"
  export ORQUESTRA_INSTALL_BUILD_SKIPPED="${SKIP_BUILD}"
  export ORQUESTRA_INSTALL_PACKAGE_VERIFIED="${VERIFY_PACKAGE}"
  export ORQUESTRA_INSTALL_RUNTIME_SYNCED="${SYNC_RUNTIME}"
  export ORQUESTRA_INSTALL_BACKUP_CREATED="${BACKUP_CREATED}"
  export ORQUESTRA_INSTALL_BACKUP_PATH="${BACKUP_PATH}"
  export ORQUESTRA_INSTALL_PREVIOUS_VERSION="${PREVIOUS_VERSION}"
  export ORQUESTRA_INSTALL_PREVIOUS_INSTALLED_AT="${PREVIOUS_INSTALLED_AT}"
  export ORQUESTRA_INSTALL_RUNTIME_CONFIG_PATH="${RUNTIME_CONFIG_PATH}"
  export ORQUESTRA_INSTALL_DATABASE_URL="sqlite:///${DB_PATH}"
  export ORQUESTRA_INSTALL_QDRANT_PATH="${RUNTIME_DIR}/experiments/orquestra/qdrant"
  /usr/bin/python3 - <<'PY'
import json
import os
import pathlib
from datetime import datetime, timezone

def as_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() == "true"

payload = {
    "app_name": os.environ["ORQUESTRA_INSTALL_APP_NAME"],
    "app_version": os.environ["ORQUESTRA_INSTALL_APP_VERSION"],
    "installed_at": datetime.now(timezone.utc).isoformat(),
    "source_root": os.environ["ORQUESTRA_INSTALL_SOURCE_ROOT"],
    "install_dir": os.environ["ORQUESTRA_INSTALL_TARGET_APP"],
    "app_shortcut": os.environ["ORQUESTRA_INSTALL_APP_SHORTCUT"],
    "uninstaller_app": os.environ["ORQUESTRA_INSTALL_UNINSTALLER_APP"],
    "runtime_dir": os.environ["ORQUESTRA_INSTALL_RUNTIME_DIR"],
    "support_dir": os.environ["ORQUESTRA_INSTALL_SUPPORT_DIR"],
    "logs_dir": os.environ["ORQUESTRA_INSTALL_LOG_DIR"],
    "api_url": os.environ["ORQUESTRA_INSTALL_API_URL"],
    "launch_agent_label": os.environ["ORQUESTRA_INSTALL_LAUNCH_AGENT"],
    "build_skipped": as_bool("ORQUESTRA_INSTALL_BUILD_SKIPPED"),
    "package_verified": as_bool("ORQUESTRA_INSTALL_PACKAGE_VERIFIED"),
    "runtime_synced": as_bool("ORQUESTRA_INSTALL_RUNTIME_SYNCED"),
    "backup_created": as_bool("ORQUESTRA_INSTALL_BACKUP_CREATED"),
    "backup_path": os.environ.get("ORQUESTRA_INSTALL_BACKUP_PATH") or None,
    "previous_app_version": os.environ.get("ORQUESTRA_INSTALL_PREVIOUS_VERSION") or None,
    "previous_installed_at": os.environ.get("ORQUESTRA_INSTALL_PREVIOUS_INSTALLED_AT") or None,
}
path = pathlib.Path(os.environ["ORQUESTRA_INSTALL_MANIFEST_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

runtime_config = {
    "version": 1,
    "runtime_dir": os.environ["ORQUESTRA_INSTALL_RUNTIME_DIR"],
    "data_root": str(pathlib.Path(os.environ["ORQUESTRA_INSTALL_RUNTIME_DIR"]) / "experiments" / "orquestra"),
    "database_url": os.environ["ORQUESTRA_INSTALL_DATABASE_URL"],
    "qdrant_path": os.environ["ORQUESTRA_INSTALL_QDRANT_PATH"],
    "storage_policy": "local_processing_hub",
    "installed_at": payload["installed_at"],
}
config_path = pathlib.Path(os.environ["ORQUESTRA_INSTALL_RUNTIME_CONFIG_PATH"])
config_path.parent.mkdir(parents=True, exist_ok=True)
config_path.write_text(json.dumps(runtime_config, ensure_ascii=False, indent=2), encoding="utf-8")
try:
    config_path.chmod(0o600)
except OSError:
    pass
PY
else
  echo "[orquestra-install] runtime sync desativado (--no-runtime-sync)"
fi

if [[ ! -x "${RUNTIME_DIR}/scripts/start_orquestra_api.sh" ]]; then
  echo "[orquestra-install] runtime local invalido; script da API ausente em ${RUNTIME_DIR}" >&2
  exit 1
fi

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
    <string>-c</string>
    <string>exec "${RUNTIME_DIR}/scripts/start_orquestra_api.sh"</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${RUNTIME_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ORQUESTRA_ROOT</key>
    <string>${RUNTIME_DIR}</string>
    <key>ORQUESTRA_RUNTIME_CONFIG</key>
    <string>${RUNTIME_CONFIG_PATH}</string>
    <key>ORQUESTRA_USE_INSTALLED_RUNTIME</key>
    <string>1</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
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

plutil -lint "${LAUNCH_AGENT_PLIST}" >/dev/null
launchctl bootout "gui/${UID}" "${LAUNCH_AGENT_PLIST}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID}" "${LAUNCH_AGENT_PLIST}"
launchctl kickstart -k "gui/${UID}/${LAUNCH_AGENT_LABEL}" >/dev/null 2>&1 || true

if [[ "${WAIT_API}" == "true" ]]; then
  echo "[orquestra-install] aguardando API local"
  WAIT_SECONDS="${ORQUESTRA_INSTALL_API_WAIT_SECONDS:-90}"
  for ((i = 1; i <= WAIT_SECONDS; i++)); do
    if curl -fsS "${API_URL}" >/dev/null 2>&1; then
      echo "[orquestra-install] API pronta em ${API_URL}"
      break
    fi
    if [[ "${i}" -eq "${WAIT_SECONDS}" ]]; then
      echo "[orquestra-install] a API não respondeu após a instalação" >&2
      echo "[orquestra-install] consulte: ${LOG_DIR}/api.stderr.log" >&2
      exit 1
    fi
    sleep 1
  done
else
  echo "[orquestra-install] pulando espera da API (--no-wait-api)"
fi

if [[ "${OPEN_APP}" == "true" ]]; then
  echo "[orquestra-install] abrindo app instalado"
  /usr/bin/open -n "${INSTALL_DIR}"
fi

if [[ -f "${DMG_PATH}" ]]; then
  echo "  dmg: ${DMG_PATH}"
fi

echo
echo "[orquestra-install] instalação concluída"
echo "  app: ${INSTALL_DIR}"
echo "  atalho app: ${APP_SHORTCUT_PATH}"
echo "  desinstalador: ${UNINSTALLER_INSTALL_DIR}"
echo "  launch agent: ${LAUNCH_AGENT_PLIST}"
echo "  logs: ${LOG_DIR}"
echo "  api: ${API_URL}"
if [[ -f "${MANIFEST_PATH}" ]]; then
  echo "  manifest: ${MANIFEST_PATH}"
fi
