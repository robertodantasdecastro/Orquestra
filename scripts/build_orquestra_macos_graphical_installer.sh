#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-graphical-build] este build e apenas para macOS" >&2
  exit 1
fi

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PACKAGE_VERSION="$(/usr/bin/python3 - <<'PY' "${ROOT_DIR}/orquestra_web/package.json"
import json, pathlib, sys
try:
    print(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")).get("version", "0.2.0"))
except Exception:
    print("0.2.0")
PY
)"
BUNDLE_DIR="${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle"
STAGE_DIR="${ROOT_DIR}/orquestra_web/src-tauri/target/release/graphical-installer-stage"
OUTPUT_DMG="${BUNDLE_DIR}/dmg/Orquestra AI Installer_${PACKAGE_VERSION}_aarch64.dmg"
BASE_APP_DMG="${BUNDLE_DIR}/dmg/Orquestra AI_${PACKAGE_VERSION}_aarch64.dmg"

echo "[orquestra-graphical-build] root=${ROOT_DIR}"
echo "[orquestra-graphical-build] version=${PACKAGE_VERSION}"

(
  cd "${ROOT_DIR}/orquestra_web"
  npm run desktop:build
  npm run desktop:build:installer
  npm run desktop:build:uninstaller
)

APP_MAIN="${BUNDLE_DIR}/macos/Orquestra AI.app"
APP_INSTALLER="${BUNDLE_DIR}/macos/Orquestra Installer.app"
APP_UNINSTALLER="${BUNDLE_DIR}/macos/Orquestra Uninstaller.app"

for app in "${APP_MAIN}" "${APP_INSTALLER}" "${APP_UNINSTALLER}"; do
  if [[ ! -d "${app}" ]]; then
    echo "[orquestra-graphical-build] app ausente: ${app}" >&2
    exit 1
  fi
done

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/.payload/orquestra_web/src-tauri/target/release/bundle/macos"
mkdir -p "${STAGE_DIR}/.payload/scripts"

ditto "${APP_MAIN}" "${STAGE_DIR}/Orquestra AI.app"
ditto "${APP_INSTALLER}" "${STAGE_DIR}/Orquestra Installer.app"
ditto "${APP_UNINSTALLER}" "${STAGE_DIR}/Orquestra Uninstaller.app"
ditto "${APP_MAIN}" "${STAGE_DIR}/.payload/orquestra_web/src-tauri/target/release/bundle/macos/Orquestra AI.app"
rsync -a "${ROOT_DIR}/scripts/" "${STAGE_DIR}/.payload/scripts/"

cat > "${STAGE_DIR}/README Instalação.txt" <<README
Orquestra AI Installer ${PACKAGE_VERSION}

1. Abra "Orquestra Installer.app" para instalar o Orquestra com wizard grafico.
2. O instalador detecta dependencias, configura runtime.json, storage, providers e LaunchAgent.
3. Abra "Orquestra Uninstaller.app" para remover seletivamente app, dados, memoria, RAG, OSINT e dependencias opcionais.
4. O app principal "Orquestra AI.app" tambem esta neste DMG para validacao visual.

Segredos nao sao impressos nem salvos no Git. Use Keychain sempre que possivel.
README

mkdir -p "${BUNDLE_DIR}/dmg"
if [[ ! -f "${BASE_APP_DMG}" ]]; then
  hdiutil create -volname "Orquestra AI" -srcfolder "${APP_MAIN}" -ov -format UDZO "${BASE_APP_DMG}" >/dev/null
fi
rm -f "${OUTPUT_DMG}"
hdiutil create -volname "Orquestra AI Installer" -srcfolder "${STAGE_DIR}" -ov -format UDZO "${OUTPUT_DMG}" >/dev/null

echo "[orquestra-graphical-build] dmg=${OUTPUT_DMG}"
