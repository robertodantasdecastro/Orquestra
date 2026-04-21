from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_settings_storage_blocks_remote_active_domain(client):
    locations = client.get("/api/settings/storage/locations")
    assert locations.status_code == 200, locations.text
    assert any(item["id"] == "local-processing-hub" for item in locations.json())

    remote = client.post(
        "/api/settings/storage/locations",
        json={
            "label": "S3 frio",
            "backend": "s3_compatible",
            "base_uri": "s3://orquestra-backups",
            "enabled": True,
            "priority": 50,
        },
    )
    assert remote.status_code == 200, remote.text

    blocked = client.put(
        "/api/settings/storage/assignments/sqlite_active",
        json={
            "location_id": remote.json()["id"],
            "mode": "cold",
            "relative_path": "orquestra_v2.db",
        },
    )
    assert blocked.status_code == 400
    assert "não podem usar" in blocked.text


def test_runtime_json_can_be_written(client, tmp_path):
    response = client.put(
        "/api/settings/runtime",
        json={
            "data_root": "/tmp/orquestra-data",
            "database_url": "sqlite:////tmp/orquestra-data/orquestra_v2.db",
            "qdrant_path": "/tmp/orquestra-data/qdrant",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    config_path = Path(payload["runtime_config_written"])
    assert config_path.exists()
    assert str(config_path).startswith(str(tmp_path))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["data_root"] == "/tmp/orquestra-data"


def test_secret_store_file_backend_does_not_echo_value(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ORQUESTRA_DISABLE_KEYCHAIN", "1")
    monkeypatch.setenv("ORQUESTRA_SECRET_FILE_DIR", str(tmp_path / "secrets"))
    response = client.post(
        "/api/settings/secrets",
        json={
            "provider_id": "openai",
            "label": "OpenAI",
            "secret_ref": "openai.api_key",
            "value": "sk-test-secret",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["configured"] is True
    assert "sk-test-secret" not in response.text


def test_installer_json_contracts_are_available():
    root = Path(__file__).resolve().parents[1]
    install = subprocess.run(
        [str(root / "scripts/install_orquestra_macos_full.sh"), "--check-only", "--json"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    install_payload = json.loads(install.stdout)
    assert install_payload["kind"] == "InstallPlan"
    assert install_payload["steps"]

    uninstall = subprocess.run(
        [str(root / "scripts/uninstall_orquestra_macos_full.sh"), "--dry-run", "--json"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    uninstall_payload = json.loads(uninstall.stdout)
    assert uninstall_payload["kind"] == "UninstallPlan"
    assert any(item["id"] == "memory" for item in uninstall_payload["items"])
