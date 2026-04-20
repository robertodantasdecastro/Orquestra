from __future__ import annotations

MEMORY_KINDS = {
    "user",
    "feedback",
    "project",
    "reference",
    "persona",
    "dataset",
}

SCOPE_TO_MEMORY_KIND = {
    "session_memory": "user",
    "episodic_memory": "project",
    "semantic_memory": "project",
    "workspace_memory": "reference",
    "persona_memory": "persona",
    "source_fact": "reference",
    "training_signal": "dataset",
    "project_memory": "project",
}

PRESET_TO_MEMORY_KIND = {
    "research": "reference",
    "osint": "reference",
    "persona": "persona",
    "assistant": "user",
    "dataset": "dataset",
}


def normalize_memory_kind(raw_kind: str | None, *, default: str = "project") -> str:
    candidate = (raw_kind or "").strip().lower()
    if candidate in MEMORY_KINDS:
        return candidate
    return default if default in MEMORY_KINDS else "project"


def default_memory_kind_for_scope(scope: str | None) -> str:
    return normalize_memory_kind(SCOPE_TO_MEMORY_KIND.get((scope or "").strip().lower()), default="project")


def default_memory_kind_for_preset(preset: str | None) -> str:
    return normalize_memory_kind(PRESET_TO_MEMORY_KIND.get((preset or "").strip().lower()), default="project")
