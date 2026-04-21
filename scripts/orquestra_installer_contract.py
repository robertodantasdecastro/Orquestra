#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def root_dir() -> Path:
    return Path(os.getenv("ORQUESTRA_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()


def app_version(root: Path) -> str:
    package_json = root / "orquestra_web" / "package.json"
    try:
        return str(json.loads(package_json.read_text(encoding="utf-8")).get("version") or "0.2.0")
    except Exception:
        return "0.2.0"


def runtime_dir() -> Path:
    return Path(os.getenv("ORQUESTRA_RUNTIME_DIR", Path.home() / "Library" / "Application Support" / "Orquestra" / "runtime")).expanduser()


def command_status(command: str) -> dict[str, Any]:
    path = shutil.which(command)
    return {"command": command, "installed": bool(path), "path": path or "", "required": True}


def file_status(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0}


def installed_paths(root: Path) -> dict[str, str]:
    version = app_version(root)
    runtime = runtime_dir()
    return {
        "app_bundle": str(root / "orquestra_web" / "src-tauri" / "target" / "release" / "bundle" / "macos" / "Orquestra AI.app"),
        "dmg": str(root / "orquestra_web" / "src-tauri" / "target" / "release" / "bundle" / "dmg" / f"Orquestra AI_{version}_aarch64.dmg"),
        "graphical_dmg": str(root / "orquestra_web" / "src-tauri" / "target" / "release" / "bundle" / "dmg" / f"Orquestra AI Installer_{version}_aarch64.dmg"),
        "installed_app": str(Path.home() / "Applications" / "Orquestra AI.app"),
        "runtime": str(runtime),
        "runtime_config": str(runtime / "config" / "runtime.json"),
        "database": str(runtime / "experiments" / "orquestra" / "orquestra_v2.db"),
        "memory": str(runtime / "experiments" / "orquestra" / "memorygraph"),
        "rag": str(runtime / "experiments" / "orquestra" / "rag_runtime"),
        "osint": str(runtime / "experiments" / "orquestra" / "osint"),
        "workspace": str(runtime / "experiments" / "orquestra" / "workspace"),
        "workflows": str(runtime / "experiments" / "orquestra" / "workflows"),
        "trainplane": str(runtime / "experiments" / "orquestra" / "trainplane"),
        "logs": str(Path.home() / "Library" / "Logs" / "Orquestra"),
        "launch_agent": str(Path.home() / "Library" / "LaunchAgents" / "ai.orquestra.api.plist"),
    }


def build_install_plan() -> dict[str, Any]:
    root = root_dir()
    paths = installed_paths(root)
    commands = ["xcode-select", "brew", "python3.12", "node", "npm", "cargo", "rustc", "uv", "git"]
    dependencies = [command_status(item) for item in commands]
    optional = [
        {"id": "lmstudio", "label": "LM Studio", "required": False, "configured": bool(shutil.which("lmstudio"))},
        {"id": "ollama", "label": "Ollama", "required": False, "configured": bool(shutil.which("ollama"))},
        {"id": "tor", "label": "Tor proxy", "required": False, "configured": bool(shutil.which("tor"))},
        {"id": "ffmpeg", "label": "ffmpeg", "required": False, "configured": bool(shutil.which("ffmpeg"))},
        {"id": "brave", "label": "Brave Browser", "required": False, "configured": Path("/Applications/Brave Browser.app").exists()},
    ]
    provider_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "BRAVE_SEARCH_API_KEY",
        "TAVILY_API_KEY",
        "EXA_API_KEY",
        "YOUTUBE_API_KEY",
        "SHODAN_API_KEY",
        "CENSYS_API_ID",
        "CENSYS_API_SECRET",
    ]
    return {
        "kind": "InstallPlan",
        "generated_at": now(),
        "platform": {"system": platform.system(), "machine": platform.machine(), "release": platform.release()},
        "root": str(root),
        "version": app_version(root),
        "paths": paths,
        "dependencies": dependencies,
        "optional_features": optional,
        "providers": [{"env": item, "configured": bool(os.getenv(item)), "secret_output": False} for item in provider_keys],
        "runtime_storage": {
            "default_runtime": str(runtime_dir()),
            "shared_runtime": "/Library/Application Support/Orquestra/runtime",
            "active_storage_allowed_backends": ["local_path", "external_drive", "cloud_mounted"],
            "cold_storage_allowed_backends": ["s3_compatible", "sftp", "readonly_archive"],
        },
        "steps": [
            {"id": "preflight", "label": "Diagnosticar macOS e dependências"},
            {"id": "dependencies", "label": "Instalar dependências obrigatórias autorizadas"},
            {"id": "runtime", "label": "Criar runtime.json e diretórios de dados"},
            {"id": "app", "label": "Instalar Orquestra AI.app"},
            {"id": "launch_agent", "label": "Registrar LaunchAgent da API"},
            {"id": "validate", "label": "Validar API, web, app e providers"},
        ],
    }


def build_uninstall_plan(mode: str = "safe") -> dict[str, Any]:
    root = root_dir()
    paths = installed_paths(root)
    item_order = [
        ("app", "App instalado", paths["installed_app"], True),
        ("launch_agent", "LaunchAgent da API", paths["launch_agent"], True),
        ("runtime_all", "Runtime completo", paths["runtime"], mode != "preserve-deps"),
        ("logs", "Logs", paths["logs"], True),
        ("db", "Banco SQLite", paths["database"], mode == "all"),
        ("memory", "MemoryGraph/memdir", paths["memory"], mode == "all"),
        ("rag_indexes", "Índices RAG/Chroma", paths["rag"], mode == "all"),
        ("osint", "Evidências OSINT", paths["osint"], mode == "all"),
        ("workspace", "Workspace scans/extractions", paths["workspace"], mode == "all"),
        ("workflows", "Workflow runs", paths["workflows"], mode == "all"),
        ("trainplane", "Train Plane local", paths["trainplane"], mode == "all"),
    ]
    return {
        "kind": "UninstallPlan",
        "generated_at": now(),
        "mode": mode,
        "items": [
            {
                "id": item_id,
                "label": label,
                "path": path,
                "exists": Path(path).exists(),
                "selected": selected,
                "sensitive": item_id in {"db", "memory", "rag_indexes", "osint", "workspace"},
                "backup_recommended": item_id in {"db", "memory", "rag_indexes", "osint", "workspace"},
            }
            for item_id, label, path, selected in item_order
        ],
        "dependencies": [
            {"id": "brew_python", "label": "Homebrew python@3.12", "selected": mode == "all"},
            {"id": "brew_node", "label": "Homebrew node", "selected": mode == "all"},
            {"id": "brew_rust", "label": "Homebrew rust", "selected": mode == "all"},
            {"id": "brew_uv", "label": "Homebrew uv", "selected": mode == "all"},
            {"id": "brew_tor", "label": "Homebrew tor", "selected": mode == "all"},
            {"id": "brew_ollama", "label": "Homebrew ollama", "selected": mode == "all"},
            {"id": "cask_brave", "label": "Brave Browser", "selected": mode == "all"},
            {"id": "cask_lmstudio", "label": "LM Studio", "selected": mode == "all"},
        ],
        "strong_confirmation_required": mode == "all",
    }


def build_check_report() -> dict[str, Any]:
    plan = build_install_plan()
    paths = plan["paths"]
    return {
        "kind": "InstallationCheck",
        "generated_at": now(),
        "platform": plan["platform"],
        "dependencies": plan["dependencies"],
        "artifacts": {
            key: file_status(Path(value))
            for key, value in paths.items()
            if key in {"app_bundle", "dmg", "graphical_dmg", "installed_app", "runtime_config", "database"}
        },
        "runtime": {
            "runtime_dir": paths["runtime"],
            "runtime_exists": Path(paths["runtime"]).exists(),
            "sqlite_ok": _sqlite_ok(Path(paths["database"])),
        },
    }


def _sqlite_ok(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with sqlite3.connect(path) as connection:
            connection.execute("select 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def emit_event(step_id: str, status: str, message: str, **extra: Any) -> None:
    print(json.dumps({"kind": "InstallStepEvent", "step_id": step_id, "status": status, "message": message, **extra}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["install-plan", "uninstall-plan", "check", "emit-smoke"])
    parser.add_argument("--mode", default="safe")
    args = parser.parse_args()
    if args.command == "install-plan":
        print(json.dumps(build_install_plan(), ensure_ascii=False, indent=2))
    elif args.command == "uninstall-plan":
        print(json.dumps(build_uninstall_plan(args.mode), ensure_ascii=False, indent=2))
    elif args.command == "check":
        print(json.dumps(build_check_report(), ensure_ascii=False, indent=2))
    elif args.command == "emit-smoke":
        emit_event("preflight", "running", "Validando contratos do instalador.")
        emit_event("preflight", "succeeded", "Contratos JSON disponíveis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

