"""LLM provider registry with OpenAI-compatible domestic and international endpoints.

All listed providers expose an OpenAI-compatible chat completions API, so we can
drive them with the ``openai`` package by swapping ``base_url`` and ``api_key``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.secrets import get_secrets_manager


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    name: str
    display_name: str
    base_url: str
    api_key_env: str
    secret_key: str  # key inside secrets manager namespace "llm"
    default_models: List[str]
    secret_namespace: str = "llm"

    def resolve_api_key(self) -> Optional[str]:
        """Return API key from environment, then secrets manager."""
        env_key = os.environ.get(self.api_key_env)
        if env_key:
            return env_key
        try:
            return get_secrets_manager().get(self.secret_key, namespace=self.secret_namespace)
        except Exception:
            return None

    def is_configured(self) -> bool:
        return bool(self.resolve_api_key())


class ProviderRegistry:
    """Registry of supported LLM providers."""

    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(
            ProviderConfig(
                name="openai",
                display_name="OpenAI",
                base_url="https://api.openai.com/v1",
                api_key_env="OPENAI_API_KEY",
                secret_key="OPENAI_API_KEY",
                default_models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            )
        )
        self.register(
            ProviderConfig(
                name="anthropic",
                display_name="Anthropic (OpenAI-compatible)",
                base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
                api_key_env="ANTHROPIC_API_KEY",
                secret_key="ANTHROPIC_API_KEY",
                default_models=["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            )
        )
        # Domestic / China-friendly providers (OpenAI-compatible)
        self.register(
            ProviderConfig(
                name="deepseek",
                display_name="DeepSeek",
                base_url="https://api.deepseek.com",
                api_key_env="DEEPSEEK_API_KEY",
                secret_key="DEEPSEEK_API_KEY",
                default_models=["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
            )
        )
        self.register(
            ProviderConfig(
                name="qwen",
                display_name="通义千问 (DashScope)",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key_env="DASHSCOPE_API_KEY",
                secret_key="DASHSCOPE_API_KEY",
                default_models=["qwen-turbo", "qwen-plus", "qwen-max"],
            )
        )
        self.register(
            ProviderConfig(
                name="zhipu",
                display_name="智谱 GLM",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key_env="ZHIPU_API_KEY",
                secret_key="ZHIPU_API_KEY",
                default_models=["glm-4", "glm-4-flash", "glm-4-air"],
            )
        )
        self.register(
            ProviderConfig(
                name="moonshot",
                display_name="Moonshot (Kimi)",
                base_url="https://api.moonshot.cn/v1",
                api_key_env="MOONSHOT_API_KEY",
                secret_key="MOONSHOT_API_KEY",
                default_models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
            )
        )
        self.register(
            ProviderConfig(
                name="azure",
                display_name="Azure OpenAI",
                base_url=os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
                api_key_env="AZURE_OPENAI_KEY",
                secret_key="AZURE_OPENAI_KEY",
                default_models=["gpt-4o", "gpt-4o-mini"],
            )
        )
        # Local / self-hosted
        self.register(
            ProviderConfig(
                name="ollama",
                display_name="Ollama / Local",
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                api_key_env="OLLAMA_API_KEY",
                secret_key="OLLAMA_API_KEY",
                default_models=["llama3.1", "qwen2.5", "deepseek-coder-v2"],
            )
        )

    def register(self, config: ProviderConfig) -> None:
        self._providers[config.name] = config

    def get(self, name: str) -> Optional[ProviderConfig]:
        return self._providers.get(name)

    def list(self) -> List[ProviderConfig]:
        return list(self._providers.values())

    def list_configured(self) -> List[ProviderConfig]:
        return [p for p in self._providers.values() if p.is_configured()]

    def infer_provider(self, model: str) -> Optional[ProviderConfig]:
        """Infer provider from model name or settings."""
        # Explicit provider setting takes precedence.
        explicit = os.environ.get("HOMOMICS_LLM_PROVIDER")
        if explicit:
            return self.get(explicit)
        explicit_setting = getattr(settings, "llm_provider", None)
        if explicit_setting:
            return self.get(explicit_setting)

        model_lower = model.lower()
        # International
        if model_lower.startswith("gpt") or model_lower.startswith("o1") or model_lower.startswith("o3"):
            return self.get("openai")
        if model_lower.startswith("claude"):
            return self.get("anthropic")
        # Domestic
        if model_lower.startswith("deepseek"):
            return self.get("deepseek")
        if model_lower.startswith("qwen"):
            return self.get("qwen")
        if model_lower.startswith("glm"):
            return self.get("zhipu")
        if model_lower.startswith("moonshot"):
            return self.get("moonshot")
        # Azure uses OpenAI model names but custom endpoint.
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if azure_endpoint:
            return self.get("azure")
        # Default to openai for unknown models (best effort).
        return self.get("openai")


# Module-level singleton.
_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
