#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[orquestra-graphical-validate] este validador e apenas para macOS" >&2
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
APP_MAIN="${BUNDLE_DIR}/macos/Orquestra AI.app"
APP_INSTALLER="${BUNDLE_DIR}/macos/Orquestra Installer.app"
APP_UNINSTALLER="${BUNDLE_DIR}/macos/Orquestra Uninstaller.app"
OUTPUT_DMG="${BUNDLE_DIR}/dmg/Orquestra AI Installer_${PACKAGE_VERSION}_aarch64.dmg"

check_exists() {
  local label="$1"
  local path="$2"
  if [[ ! -e "${path}" ]]; then
    echo "[orquestra-graphical-validate] missing ${label}: ${path}" >&2
    exit 1
  fi
  echo "[orquestra-graphical-validate] ok ${label}: ${path}"
}

check_exists "tauri installer config" "${ROOT_DIR}/orquestra_web/src-tauri/tauri.installer.conf.json"
check_exists "tauri uninstaller config" "${ROOT_DIR}/orquestra_web/src-tauri/tauri.uninstaller.conf.json"
check_exists "app principal" "${APP_MAIN}"
check_exists "app installer" "${APP_INSTALLER}"
check_exists "app uninstaller" "${APP_UNINSTALLER}"
check_exists "dmg grafico" "${OUTPUT_DMG}"

bash -n \
  "${ROOT_DIR}/scripts/install_orquestra_macos_full.sh" \
  "${ROOT_DIR}/scripts/uninstall_orquestra_macos_full.sh" \
  "${ROOT_DIR}/scripts/build_orquestra_macos_graphical_installer.sh" \
  "${ROOT_DIR}/scripts/validate_orquestra_macos_graphical_installer.sh"

for app in "${APP_MAIN}" "${APP_INSTALLER}" "${APP_UNINSTALLER}"; do
  codesign -dv "${app}" >/tmp/orquestra-codesign.txt 2>&1 || true
  if ! grep -q "Signature=" /tmp/orquestra-codesign.txt; then
    echo "[orquestra-graphical-validate] assinatura local ausente em ${app}" >&2
    cat /tmp/orquestra-codesign.txt >&2 || true
    exit 1
  fi
  if grep -q "TeamIdentifier=not set" /tmp/orquestra-codesign.txt; then
    echo "[orquestra-graphical-validate] notarizacao: ausente/nao Developer ID para ${app}; ok para V1 local"
  fi
done

python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" install-plan >/dev/null
python3 "${ROOT_DIR}/scripts/orquestra_installer_contract.py" uninstall-plan >/dev/null

echo "[orquestra-graphical-validate] instalador grafico validado para uso local"
