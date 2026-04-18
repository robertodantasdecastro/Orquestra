from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .gateway import RagGateway, RagGatewayError, RagGatewayProvider


class RagLlmError(RuntimeError):
    """Erro operacional do cliente de LLM."""


@dataclass
class LlmResponse:
    content: str
    model_name: str
    latency_seconds: float
    usage: dict[str, Any]
    provider_id: str


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _default_gateway_providers() -> list[RagGatewayProvider]:
    return [
        RagGatewayProvider(
            provider_id="lmstudio",
            label="LM Studio Local",
            transport="openai_compatible",
            base_url=_env("LMSTUDIO_API_BASE", "http://localhost:1234/v1"),
            api_key_env="LMSTUDIO_API_KEY",
            default_model=_env("DEFAULT_MODEL", "ministral"),
            model_prefix="openai",
            capabilities=["chat", "streaming", "structured_output", "local_only"],
            config={"mode": "gui_or_headless"},
        ),
        RagGatewayProvider(
            provider_id="openai",
            label="OpenAI",
            transport="litellm",
            base_url=os.getenv("ORQUESTRA_LITELLM_PROXY_URL") or None,
            api_key_env="OPENAI_API_KEY",
            default_model=_env("ORQUESTRA_OPENAI_MODEL", "gpt-4.1-mini"),
            model_prefix="openai",
            capabilities=["chat", "streaming", "tool_calling", "structured_output", "vision", "reasoning"],
            config={"budget_enabled": True},
        ),
        RagGatewayProvider(
            provider_id="anthropic",
            label="Anthropic Claude",
            transport="litellm",
            base_url=os.getenv("ORQUESTRA_LITELLM_PROXY_URL") or None,
            api_key_env="ANTHROPIC_API_KEY",
            default_model=_env("ORQUESTRA_ANTHROPIC_MODEL", "claude-3-7-sonnet-latest"),
            model_prefix="anthropic",
            capabilities=["chat", "streaming", "tool_calling", "structured_output", "vision", "reasoning"],
            config={"prefer_native_tool_use": True},
        ),
        RagGatewayProvider(
            provider_id="deepseek",
            label="DeepSeek",
            transport="litellm",
            base_url=os.getenv("ORQUESTRA_LITELLM_PROXY_URL") or _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            api_key_env="DEEPSEEK_API_KEY",
            default_model=_env("ORQUESTRA_DEEPSEEK_MODEL", "deepseek-chat"),
            model_prefix="deepseek",
            capabilities=["chat", "streaming", "reasoning", "remote_only"],
            config={"low_cost": True},
        ),
        RagGatewayProvider(
            provider_id="ollama",
            label="Ollama",
            transport="litellm",
            base_url=os.getenv("ORQUESTRA_LITELLM_PROXY_URL") or _env("ORQUESTRA_OLLAMA_BASE_URL", "http://localhost:11434"),
            api_key_env="OLLAMA_API_KEY",
            default_model=_env("ORQUESTRA_OLLAMA_MODEL", "qwen3:8b"),
            model_prefix="ollama",
            capabilities=["chat", "streaming", "local_only"],
            config={"optional": True},
        ),
    ]


class LMStudioClient:
    """
    Cliente compatível com o pipeline RAG antigo, agora apoiado no gateway multi-provider.

    O nome foi mantido para evitar quebrar imports já existentes.
    """

    def __init__(self, *, mock: bool = False, provider_id: str | None = None) -> None:
        self.provider_id = provider_id or os.getenv("ORQUESTRA_DEFAULT_PROVIDER", "lmstudio")
        self.default_model = os.getenv("DEFAULT_MODEL", "ministral")
        self.mock = mock or os.getenv("RAG_MOCK_LLM", "false").lower() == "true"
        self.gateway = RagGateway(_default_gateway_providers(), mock=self.mock)

    def list_models(self) -> list[str]:
        try:
            return self.gateway.list_models(self.provider_id)
        except RagGatewayError as exc:
            raise RagLlmError(f"Falha ao listar modelos no provider {self.provider_id}: {exc}") from exc

    def generate(
        self,
        *,
        messages: list[dict[str, str]],
        model_name: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
        fallback_text: str = "",
    ) -> LlmResponse:
        chosen_model = model_name or self.default_model
        try:
            response = self.gateway.generate(
                messages=messages,
                provider_id=self.provider_id,
                model_name=chosen_model,
                temperature=temperature,
                max_tokens=max_tokens,
                fallback_text=fallback_text,
            )
        except RagGatewayError as exc:
            raise RagLlmError(f"Falha ao gerar resposta via provider {self.provider_id}: {exc}") from exc

        return LlmResponse(
            content=response.content,
            model_name=response.model_name,
            latency_seconds=response.latency_seconds,
            usage=response.usage,
            provider_id=response.provider_id,
        )
