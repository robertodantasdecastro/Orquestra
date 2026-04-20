#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-package] validação de pacote disponível apenas no macOS" >&2
  exit 1
fi

ROOT_DIR="${ORQUESTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_NAME="Orquestra AI.app"
APP_BUNDLE="${ORQUESTRA_APP_BUNDLE:-${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/macos/${APP_NAME}}"
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
DMG_PATH="${ORQUESTRA_DMG_PATH:-${ROOT_DIR}/orquestra_web/src-tauri/target/release/bundle/dmg/Orquestra AI_${PACKAGE_VERSION}_aarch64.dmg}"
INFO_PLIST="${APP_BUNDLE}/Contents/Info.plist"
EXECUTABLE="${APP_BUNDLE}/Contents/MacOS/orquestra-desktop"
INSTALLER="${ROOT_DIR}/scripts/install_orquestra_macos.sh"
UNINSTALLER="${ROOT_DIR}/scripts/uninstall_orquestra_macos.sh"

echo "[orquestra-package] root: ${ROOT_DIR}"

if [[ ! -d "${APP_BUNDLE}" ]]; then
  echo "[orquestra-package] app bundle ausente: ${APP_BUNDLE}" >&2
  exit 1
fi

if [[ ! -f "${INFO_PLIST}" ]]; then
  echo "[orquestra-package] Info.plist ausente: ${INFO_PLIST}" >&2
  exit 1
fi

if [[ ! -x "${EXECUTABLE}" ]]; then
  echo "[orquestra-package] executável ausente ou sem permissão: ${EXECUTABLE}" >&2
  exit 1
fi

plutil -lint "${INFO_PLIST}" >/dev/null

BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${INFO_PLIST}")"
BUNDLE_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "${INFO_PLIST}")"
BUNDLE_EXECUTABLE="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "${INFO_PLIST}")"

echo "[orquestra-package] app: ${APP_BUNDLE}"
echo "[orquestra-package] bundle id: ${BUNDLE_ID}"
echo "[orquestra-package] versão: ${BUNDLE_VERSION}"
echo "[orquestra-package] executável: ${BUNDLE_EXECUTABLE}"

if [[ -f "${DMG_PATH}" ]]; then
  hdiutil imageinfo "${DMG_PATH}" >/dev/null
  echo "[orquestra-package] dmg: ${DMG_PATH}"
else
  echo "[orquestra-package] dmg ausente: ${DMG_PATH}" >&2
  exit 1
fi

bash -n "${INSTALLER}"
bash -n "${UNINSTALLER}"
[[ -x "${INSTALLER}" ]] || chmod +x "${INSTALLER}"
[[ -x "${UNINSTALLER}" ]] || chmod +x "${UNINSTALLER}"

if codesign --verify --deep --strict --verbose=2 "${APP_BUNDLE}" >/dev/null 2>&1; then
  echo "[orquestra-package] assinatura local: válida"
else
  echo "[orquestra-package] assinatura local: ad-hoc/não notarizada; ok para uso local, não para distribuição pública"
  codesign -dv "${APP_BUNDLE}" 2>&1 | sed 's/^/[orquestra-package] codesign: /' || true
fi

echo "[orquestra-package] pacote macOS validado para uso local"
