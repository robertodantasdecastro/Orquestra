from __future__ import annotations

import copy
import json
from typing import Any

from .models import ChatSession

SESSION_PROFILE_KEY = "orquestra_session_profile"

PRESET_LABELS: dict[str, str] = {
    "research": "Pesquisa",
    "osint": "OSINT",
    "persona": "Persona",
    "assistant": "Assistente",
    "dataset": "Dataset",
}

VALID_PRESETS = set(PRESET_LABELS)

DEFAULT_MEMORY_POLICY: dict[str, Any] = {
    "enabled": True,
    "auto_capture": True,
    "review_required": True,
    "use_in_prompt": True,
    "generate_training_candidates": False,
    "retention": "durable_after_approval",
    "scopes": [
        "session_memory",
        "episodic_memory",
        "semantic_memory",
        "workspace_memory",
        "persona_memory",
        "source_fact",
        "training_signal",
    ],
}

DEFAULT_RAG_POLICY: dict[str, Any] = {
    "enabled": True,
    "collections": ["knowledge_base", "security_base"],
    "memory_collection": "orquestra_memory_v1",
    "include_memory": True,
    "include_workspace": True,
    "include_sources": True,
    "top_k_memory": 6,
    "top_k_sources": 4,
    "top_k_workspace": 4,
    "max_context_chars": 9000,
}

DEFAULT_PERSONA_CONFIG: dict[str, Any] = {
    "tone": "",
    "style_notes": "",
    "constraints": [],
    "source_refs": [],
}

PRESET_DEFAULTS: dict[str, dict[str, Any]] = {
    "research": {
        "memory_policy": {"generate_training_candidates": False},
        "rag_policy": {"include_sources": True, "include_workspace": True, "top_k_memory": 6},
        "persona_config": {"style_notes": "Priorizar continuidade, fontes locais, citações e resumo de descobertas."},
    },
    "osint": {
        "memory_policy": {"generate_training_candidates": False},
        "rag_policy": {"include_sources": True, "include_workspace": True, "top_k_memory": 6},
        "persona_config": {"style_notes": "Separar evidência, hipótese, data, confiança e cadeia de inferência."},
    },
    "persona": {
        "memory_policy": {"generate_training_candidates": False, "scopes": ["persona_memory", "session_memory", "semantic_memory"]},
        "rag_policy": {"include_sources": True, "include_workspace": True, "top_k_memory": 8},
        "persona_config": {"style_notes": "Assimilar tom, vocabulário, restrições e exemplos aprovados."},
    },
    "assistant": {
        "memory_policy": {"generate_training_candidates": False},
        "rag_policy": {"include_sources": True, "include_workspace": True, "top_k_memory": 6},
        "persona_config": {"style_notes": "Priorizar preferências do usuário, modo de trabalho e comandos recorrentes."},
    },
    "dataset": {
        "memory_policy": {"generate_training_candidates": True, "scopes": ["training_signal", "session_memory", "semantic_memory"]},
        "rag_policy": {"include_sources": True, "include_workspace": True, "top_k_memory": 6},
        "persona_config": {"style_notes": "Priorizar pares instrução/contexto/resposta e critérios para fine-tuning futuro."},
    },
}


def _safe_json_loads(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _deep_merge(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(base, dict):
        base = {}
    merged = copy.deepcopy(base)
    if not isinstance(override, dict) or not override:
        return merged
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def normalize_preset(raw_preset: str | None) -> str:
    preset = (raw_preset or "assistant").strip().lower()
    return preset if preset in VALID_PRESETS else "assistant"


def preset_defaults(preset: str | None) -> dict[str, Any]:
    normalized = normalize_preset(preset)
    defaults = PRESET_DEFAULTS.get(normalized, {})
    return {
        "memory_policy": _deep_merge(DEFAULT_MEMORY_POLICY, defaults.get("memory_policy")),
        "rag_policy": _deep_merge(DEFAULT_RAG_POLICY, defaults.get("rag_policy")),
        "persona_config": _deep_merge(DEFAULT_PERSONA_CONFIG, defaults.get("persona_config")),
    }


def normalize_session_profile(
    metadata: dict[str, Any] | None = None,
    *,
    objective: str | None = None,
    preset: str | None = None,
    memory_policy: dict[str, Any] | None = None,
    rag_policy: dict[str, Any] | None = None,
    persona_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    existing = metadata.get(SESSION_PROFILE_KEY) if isinstance(metadata.get(SESSION_PROFILE_KEY), dict) else {}
    normalized_preset = normalize_preset(preset or existing.get("preset"))
    defaults = preset_defaults(normalized_preset)
    return {
        "objective": (objective if objective is not None else existing.get("objective", "") or "").strip(),
        "preset": normalized_preset,
        "preset_label": PRESET_LABELS[normalized_preset],
        "memory_policy": _deep_merge(defaults["memory_policy"], _deep_merge(existing.get("memory_policy", {}), memory_policy)),
        "rag_policy": _deep_merge(defaults["rag_policy"], _deep_merge(existing.get("rag_policy", {}), rag_policy)),
        "persona_config": _deep_merge(defaults["persona_config"], _deep_merge(existing.get("persona_config", {}), persona_config)),
    }


def get_session_metadata(chat_session: ChatSession) -> dict[str, Any]:
    loaded = _safe_json_loads(chat_session.metadata_json, {})
    return loaded if isinstance(loaded, dict) else {}


def get_session_profile(chat_session: ChatSession) -> dict[str, Any]:
    metadata = get_session_metadata(chat_session)
    return normalize_session_profile(metadata)


def set_session_profile(
    chat_session: ChatSession,
    *,
    objective: str | None = None,
    preset: str | None = None,
    memory_policy: dict[str, Any] | None = None,
    rag_policy: dict[str, Any] | None = None,
    persona_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = get_session_metadata(chat_session)
    profile = normalize_session_profile(
        metadata,
        objective=objective,
        preset=preset,
        memory_policy=memory_policy,
        rag_policy=rag_policy,
        persona_config=persona_config,
    )
    metadata[SESSION_PROFILE_KEY] = profile
    chat_session.metadata_json = json.dumps(metadata, ensure_ascii=False)
    return profile


def profile_prompt_section(profile: dict[str, Any]) -> str:
    memory_policy = profile.get("memory_policy", {})
    rag_policy = profile.get("rag_policy", {})
    persona_config = profile.get("persona_config", {})
    return "\n".join(
        [
            f"Objetivo: {profile.get('objective') or 'nao definido'}",
            f"Preset: {profile.get('preset')} ({profile.get('preset_label')})",
            f"Memoria ativa: {bool(memory_policy.get('enabled'))}; escopos: {', '.join(memory_policy.get('scopes', []))}",
            f"RAG ativo: {bool(rag_policy.get('enabled'))}; colecoes: {', '.join(rag_policy.get('collections', []))}",
            f"Workspace ativo: {bool(rag_policy.get('include_workspace'))}",
            f"Persona/estilo: {persona_config.get('style_notes') or persona_config.get('tone') or 'padrao Orquestra'}",
        ]
    )
