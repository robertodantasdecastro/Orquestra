from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

SERVICE_NAME = "ai.orquestra.secrets"


class SecretStoreError(RuntimeError):
    pass


class SecretStoreService:
    def __init__(self, *, service_name: str = SERVICE_NAME) -> None:
        self.service_name = service_name
        self.disable_keychain = os.getenv("ORQUESTRA_DISABLE_KEYCHAIN", "").strip().lower() in {"1", "true", "yes"}
        self.file_dir = Path(os.getenv("ORQUESTRA_SECRET_FILE_DIR", Path.home() / ".orquestra-secrets")).expanduser()

    def put_secret(self, secret_ref: str, value: str) -> str:
        if not secret_ref.strip():
            raise SecretStoreError("secret_ref vazio.")
        if not value:
            raise SecretStoreError("valor vazio.")
        if self._use_file_backend():
            self._put_file(secret_ref, value)
            return secret_ref
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                self.service_name,
                "-a",
                secret_ref,
                "-w",
                value,
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise SecretStoreError(result.stderr.strip() or "Falha ao salvar segredo no Keychain.")
        return secret_ref

    def get_secret(self, secret_ref: str) -> str | None:
        if not secret_ref.strip():
            return None
        if self._use_file_backend():
            return self._get_file(secret_ref)
        result = subprocess.run(
            ["security", "find-generic-password", "-s", self.service_name, "-a", secret_ref, "-w"],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.rstrip("\n") or None

    def delete_secret(self, secret_ref: str) -> bool:
        if self._use_file_backend():
            path = self._file_path(secret_ref)
            if path.exists():
                path.unlink()
                return True
            return False
        result = subprocess.run(
            ["security", "delete-generic-password", "-s", self.service_name, "-a", secret_ref],
            text=True,
            capture_output=True,
        )
        return result.returncode == 0

    def test_secret(self, secret_ref: str) -> dict[str, Any]:
        configured = self.get_secret(secret_ref) is not None
        return {"secret_ref": secret_ref, "configured": configured, "backend": self.backend_name()}

    def backend_name(self) -> str:
        return "file" if self._use_file_backend() else "keychain"

    def _use_file_backend(self) -> bool:
        return self.disable_keychain or os.uname().sysname != "Darwin"

    def _file_path(self, secret_ref: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in secret_ref)
        return self.file_dir / f"{safe}.json"

    def _put_file(self, secret_ref: str, value: str) -> None:
        self.file_dir.mkdir(parents=True, exist_ok=True)
        payload = {"secret_ref": secret_ref, "value": value}
        path = self._file_path(secret_ref)
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def _get_file(self, secret_ref: str) -> str | None:
        path = self._file_path(secret_ref)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        value = payload.get("value")
        return str(value) if value else None

