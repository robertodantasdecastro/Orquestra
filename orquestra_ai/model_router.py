from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from .models import AgentProfile, ModelCatalogEntry, ModelRouteDecision, ModelRoutePolicy, ProviderProfile, utc_now


def _json_loads(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return fallback


def model_catalog_entry_to_dict(item: ModelCatalogEntry) -> dict[str, Any]:
    return {
        "id": item.id,
        "provider_id": item.provider_id,
        "model_name": item.model_name,
        "display_name": item.display_name or item.model_name,
        "context_window": item.context_window,
        "supports_tools": item.supports_tools,
        "routing_tags": _json_loads(item.routing_tags_json, []),
        "metadata": _json_loads(item.metadata_json, {}),
        "last_seen_at": item.last_seen_at.isoformat(),
    }


def model_route_policy_to_dict(item: ModelRoutePolicy) -> dict[str, Any]:
    return {
        "id": item.id,
        "label": item.label,
        "mode": item.mode,
        "task_type": item.task_type,
        "preset": item.preset,
        "preferred_provider_id": item.preferred_provider_id,
        "preferred_model_name": item.preferred_model_name,
        "fallback_chain": _json_loads(item.fallback_chain_json, []),
        "local_only": item.local_only,
        "enabled": item.enabled,
        "metadata": _json_loads(item.metadata_json, {}),
        "updated_at": item.updated_at.isoformat(),
    }


def agent_profile_to_dict(item: AgentProfile) -> dict[str, Any]:
    return {
        "id": item.id,
        "label": item.label,
        "description": item.description,
        "task_tags": _json_loads(item.task_tags_json, []),
        "provider_id": item.provider_id,
        "model_name": item.model_name,
        "privacy_level": item.privacy_level,
        "enabled": item.enabled,
        "metadata": _json_loads(item.metadata_json, {}),
        "updated_at": item.updated_at.isoformat(),
    }


def route_decision_to_dict(item: ModelRouteDecision) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "task_type": item.task_type,
        "mode": item.mode,
        "provider_id": item.provider_id,
        "model_name": item.model_name,
        "policy_id": item.policy_id,
        "reason": item.reason,
        "metadata": _json_loads(item.metadata_json, {}),
        "created_at": item.created_at.isoformat(),
    }


@dataclass(frozen=True)
class RouteRequest:
    session_id: str | None = None
    task_type: str = "generic"
    preset: str = ""
    local_only: bool = False
    provider_id: str | None = None
    model_name: str | None = None


class OrquestraModelRouter:
    def seed_defaults(self, session: Session) -> None:
        if session.exec(select(ModelRoutePolicy)).first() is None:
            providers = session.exec(select(ProviderProfile).where(ProviderProfile.enabled == True)).all()  # noqa: E712
            preferred = next((item for item in providers if item.provider_id == "lmstudio"), providers[0] if providers else None)
            session.add(
                ModelRoutePolicy(
                    label="Default local-first",
                    mode="fallback_chain",
                    task_type="generic",
                    preferred_provider_id=preferred.provider_id if preferred else "lmstudio",
                    preferred_model_name=preferred.default_model if preferred else "ministral",
                    fallback_chain_json=json.dumps(
                        [
                            {"provider_id": preferred.provider_id, "model_name": preferred.default_model}
                            for preferred in providers[:3]
                        ],
                        ensure_ascii=False,
                    ),
                    metadata_json=json.dumps({"created_by": "bootstrap"}, ensure_ascii=False),
                )
            )
        if session.exec(select(AgentProfile)).first() is None:
            session.add(
                AgentProfile(
                    label="Assistente Operacional",
                    description="Agente padrão para chat, RAG, OSINT e execução local-first.",
                    task_tags_json=json.dumps(["generic", "research", "osint"], ensure_ascii=False),
                    provider_id="lmstudio",
                    model_name="ministral",
                    privacy_level="local_first",
                )
            )
        session.commit()

    def refresh_catalog(self, session: Session, provider_id: str, models: list[str]) -> list[dict[str, Any]]:
        rows: list[ModelCatalogEntry] = []
        for model_name in sorted({item for item in models if item}):
            entry = session.exec(
                select(ModelCatalogEntry).where(
                    ModelCatalogEntry.provider_id == provider_id,
                    ModelCatalogEntry.model_name == model_name,
                )
            ).first()
            if entry is None:
                entry = ModelCatalogEntry(provider_id=provider_id, model_name=model_name)
            entry.last_seen_at = utc_now()
            entry.updated_at = utc_now()
            session.add(entry)
            rows.append(entry)
        session.commit()
        return [model_catalog_entry_to_dict(item) for item in rows]

    def choose(self, session: Session, request: RouteRequest) -> dict[str, Any]:
        providers = session.exec(select(ProviderProfile).where(ProviderProfile.enabled == True)).all()  # noqa: E712
        if request.local_only:
            providers = [item for item in providers if "local_only" in _json_loads(item.capabilities_json, [])]
        if request.provider_id:
            explicit = next((item for item in providers if item.provider_id == request.provider_id), None)
            if explicit:
                return self._record_decision(
                    session,
                    request,
                    explicit.provider_id,
                    request.model_name or explicit.default_model or "",
                    "Provider/model solicitados explicitamente.",
                )
        policies = session.exec(select(ModelRoutePolicy).where(ModelRoutePolicy.enabled == True)).all()  # noqa: E712
        policy = self._select_policy(policies, request)
        if policy:
            provider = next((item for item in providers if item.provider_id == policy.preferred_provider_id), None)
            if provider:
                return self._record_decision(
                    session,
                    request,
                    provider.provider_id,
                    policy.preferred_model_name or provider.default_model or "",
                    f"Política ativa: {policy.label}.",
                    policy_id=policy.id,
                    mode=policy.mode,
                )
        provider = next((item for item in providers if item.provider_id == "lmstudio"), providers[0] if providers else None)
        if provider is None:
            return {"provider_id": "lmstudio", "model_name": "ministral", "reason": "Fallback sem providers cadastrados.", "mode": "fallback"}
        return self._record_decision(
            session,
            request,
            provider.provider_id,
            request.model_name or provider.default_model or "ministral",
            "Fallback local-first do router.",
        )

    def _select_policy(self, policies: list[ModelRoutePolicy], request: RouteRequest) -> ModelRoutePolicy | None:
        exact = [item for item in policies if item.task_type == request.task_type and (not item.preset or item.preset == request.preset)]
        if exact:
            return exact[0]
        generic = [item for item in policies if item.task_type == "generic"]
        return generic[0] if generic else None

    def _record_decision(
        self,
        session: Session,
        request: RouteRequest,
        provider_id: str,
        model_name: str,
        reason: str,
        *,
        policy_id: str | None = None,
        mode: str = "single_best",
    ) -> dict[str, Any]:
        decision = ModelRouteDecision(
            session_id=request.session_id,
            task_type=request.task_type,
            mode=mode,
            provider_id=provider_id,
            model_name=model_name,
            policy_id=policy_id,
            reason=reason,
            metadata_json=json.dumps({"preset": request.preset, "local_only": request.local_only}, ensure_ascii=False),
        )
        session.add(decision)
        session.commit()
        session.refresh(decision)
        return route_decision_to_dict(decision)

