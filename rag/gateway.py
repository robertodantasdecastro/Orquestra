from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable


class RagGatewayError(RuntimeError):
    """Erro operacional ao consultar um provider de LLM no runtime do RAG."""


@dataclass
class RagGatewayResponse:
    content: str
    model_name: str
    provider_id: str
    latency_seconds: float
    usage: dict[str, Any]


@dataclass
class RagGatewayProvider:
    provider_id: str
    label: str
    transport: str
    base_url: str | None = None
    api_key_env: str | None = None
    default_model: str | None = None
    model_prefix: str | None = None
    enabled: bool = True
    capabilities: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


class RagGateway:
    def __init__(self, providers: Iterable[RagGatewayProvider], *, mock: bool = False) -> None:
        self.providers = {provider.provider_id: provider for provider in providers if provider.enabled}
        self.default_provider_id = next(iter(self.providers), "lmstudio")
        self.mock = mock

    def resolve_provider(self, provider_id: str | None = None) -> RagGatewayProvider:
        resolved = provider_id or self.default_provider_id
        provider = self.providers.get(resolved)
        if provider is None:
            raise RagGatewayError(f"Provider indisponivel: {resolved}")
        return provider

    def list_models(self, provider_id: str | None = None) -> list[str]:
        provider = self.resolve_provider(provider_id)
        if self.mock:
            return [provider.default_model or "mock-model"]
        if provider.base_url:
            try:
                payload = self._openai_like_get_models(provider)
                models = [item.get("id") for item in payload.get("data", []) if item.get("id")]
                if models:
                    return models
            except RagGatewayError:
                pass
        if provider.default_model:
            return [provider.default_model]
        return []

    def generate(
        self,
        *,
        messages: list[dict[str, str]],
        provider_id: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        fallback_text: str = "",
    ) -> RagGatewayResponse:
        provider = self.resolve_provider(provider_id)
        chosen_model = model_name or provider.default_model or "unknown-model"

        if self.mock:
            content = fallback_text.strip() or "Resposta simulada do gateway do RAG."
            prompt_tokens = max(len(" ".join(item.get("content", "") for item in messages).split()), 1)
            completion_tokens = max(len(content.split()), 1)
            return RagGatewayResponse(
                content=content,
                model_name=chosen_model,
                provider_id=provider.provider_id,
                latency_seconds=0.001,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            )

        started_at = time.perf_counter()
        if provider.transport in {"litellm", "openai_compatible"}:
            try:
                response = self._call_via_litellm(
                    provider=provider,
                    messages=messages,
                    model_name=chosen_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except RagGatewayError:
                if provider.transport == "openai_compatible":
                    response = self._call_openai_compatible(
                        provider=provider,
                        messages=messages,
                        model_name=chosen_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                else:
                    raise
        else:
            raise RagGatewayError(f"Transporte ainda nao suportado: {provider.transport}")

        latency = round(time.perf_counter() - started_at, 4)
        return RagGatewayResponse(
            content=response["content"].strip(),
            model_name=response["model_name"],
            provider_id=provider.provider_id,
            latency_seconds=latency,
            usage=response["usage"],
        )

    def _call_via_litellm(
        self,
        *,
        provider: RagGatewayProvider,
        messages: list[dict[str, str]],
        model_name: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        try:
            from litellm import completion
        except Exception as exc:  # pragma: no cover - depende do ambiente local
            raise RagGatewayError("LiteLLM nao esta instalado no ambiente atual.") from exc

        kwargs: dict[str, Any] = {
            "model": self._qualify_model(provider, model_name),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if provider.base_url:
            kwargs["api_base"] = self._normalize_base_url(provider.base_url)
        api_key = self._resolve_api_key(provider)
        if api_key:
            kwargs["api_key"] = api_key
        response = completion(**kwargs)
        message = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return {
            "content": message,
            "model_name": getattr(response, "model", model_name) or model_name,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            },
        }

    def _call_openai_compatible(
        self,
        *,
        provider: RagGatewayProvider,
        messages: list[dict[str, str]],
        model_name: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        base_url = self._normalize_base_url(provider.base_url)
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(provider),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - ambiente externo
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RagGatewayError(f"Provider {provider.provider_id} respondeu com HTTP {exc.code}: {detail}") from exc
        except Exception as exc:  # pragma: no cover - ambiente externo
            raise RagGatewayError(f"Falha ao consultar provider {provider.provider_id}: {exc}") from exc

        return {
            "content": raw["choices"][0]["message"].get("content", ""),
            "model_name": raw.get("model", model_name),
            "usage": raw.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
        }

    def _openai_like_get_models(self, provider: RagGatewayProvider) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._normalize_base_url(provider.base_url)}/models",
            headers=self._build_headers(provider),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - ambiente externo
            raise RagGatewayError(f"Falha ao listar modelos em {provider.provider_id}: {exc}") from exc

    def _normalize_base_url(self, base_url: str | None) -> str:
        if not base_url:
            raise RagGatewayError("Provider sem base_url configurada.")
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"

    def _build_headers(self, provider: RagGatewayProvider) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = self._resolve_api_key(provider)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _resolve_api_key(self, provider: RagGatewayProvider) -> str | None:
        if provider.provider_id == "lmstudio":
            return os.getenv(provider.api_key_env or "", "lm-studio") or "lm-studio"
        if provider.api_key_env:
            return os.getenv(provider.api_key_env) or None
        return None

    def _qualify_model(self, provider: RagGatewayProvider, model_name: str) -> str:
        if "/" in model_name:
            return model_name
        if provider.model_prefix:
            return f"{provider.model_prefix}/{model_name}"
        return model_name
