from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orquestra_ai.app import create_app
from orquestra_ai.config import load_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ORQUESTRA_DATABASE_URL", f"sqlite:///{tmp_path / 'orquestra-test.db'}")
    monkeypatch.setenv("ORQUESTRA_QDRANT_PATH", str(tmp_path / "qdrant"))
    monkeypatch.setenv("ORQUESTRA_APP_VERSION", "test-suite")
    app = create_app(load_settings(REPO_ROOT))
    with TestClient(app) as test_client:
        yield test_client
