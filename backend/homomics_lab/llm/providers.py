"""LLM provider registry with OpenAI-compatible domestic and international endpoints.

All listed providers expose an OpenAI-compatible chat completions API, so we can
drive them with the ``openai`` package by swapping ``base_url`` and ``api_key``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from homomics_lab.config import settings
from homomics_lab.secrets import get_secrets_manager


@dataclass
class ModelCapability:
    """Capability metadata for a model used in capability-based routing."""

    context_window: int = 0
    cost_rank: int = 99  # 1=cheapest; lower is cheaper
    supports_reasoning: bool = False
    supports_tool_calling: bool = False
    strengths: List[str] = field(default_factory=list)


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
    explicit_api_key: Optional[str] = None
    explicit_base_url: Optional[str] = None
    model_capabilities: Dict[str, ModelCapability] = field(default_factory=dict)

    @property
    def resolved_base_url(self) -> str:
        """Return the effective base URL, allowing runtime overrides."""
        if self.explicit_base_url:
            return self.explicit_base_url
        return self.base_url

    def resolve_api_key(self) -> Optional[str]:
        """Return API key from explicit value, environment, then secrets manager."""
        if self.explicit_api_key:
            return self.explicit_api_key
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
                model_capabilities={
                    "gpt-4o": ModelCapability(
                        context_window=128_000,
                        cost_rank=3,
                        supports_reasoning=False,
                        supports_tool_calling=True,
                        strengths=["analysis", "coding", "reasoning"],
                    ),
                    "gpt-4o-mini": ModelCapability(
                        context_window=128_000,
                        cost_rank=1,
                        supports_tool_calling=True,
                        strengths=["classification", "cheap"],
                    ),
                },
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
                model_capabilities={
                    "claude-3-5-sonnet-20241022": ModelCapability(
                        context_window=200_000,
                        cost_rank=3,
                        strengths=["analysis", "coding", "long_context"],
                    ),
                },
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
                model_capabilities={
                    "deepseek-reasoner": ModelCapability(
                        cost_rank=2,
                        supports_reasoning=True,
                        strengths=["reasoning", "coding"],
                    ),
                    "deepseek-chat": ModelCapability(
                        cost_rank=1,
                        strengths=["classification", "cheap"],
                    ),
                },
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
                model_capabilities={
                    "qwen-max": ModelCapability(
                        context_window=32_000,
                        cost_rank=3,
                        strengths=["analysis", "coding"],
                    ),
                    "qwen-turbo": ModelCapability(
                        context_window=128_000,
                        cost_rank=1,
                        strengths=["classification", "cheap"],
                    ),
                },
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
                model_capabilities={
                    "glm-4": ModelCapability(
                        context_window=128_000,
                        cost_rank=2,
                        strengths=["analysis"],
                    ),
                    "glm-4-flash": ModelCapability(
                        cost_rank=1,
                        strengths=["classification", "cheap"],
                    ),
                },
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
                model_capabilities={
                    "moonshot-v1-128k": ModelCapability(
                        context_window=128_000,
                        cost_rank=2,
                        strengths=["long_context", "analysis"],
                    ),
                    "moonshot-v1-8k": ModelCapability(
                        cost_rank=1,
                        strengths=["classification", "cheap"],
                    ),
                },
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
                model_capabilities={
                    "gpt-4o": ModelCapability(
                        context_window=128_000,
                        cost_rank=3,
                        supports_reasoning=False,
                        supports_tool_calling=True,
                        strengths=["analysis", "coding", "reasoning"],
                    ),
                    "gpt-4o-mini": ModelCapability(
                        context_window=128_000,
                        cost_rank=1,
                        supports_tool_calling=True,
                        strengths=["classification", "cheap"],
                    ),
                },
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

    def list_models_with_capabilities(
        self,
    ) -> Iterator[Tuple[str, str, ModelCapability]]:
        """Yield (provider_name, model, capability) tuples for configured providers."""
        for provider in self.list_configured():
            for model in provider.default_models:
                capability = provider.model_capabilities.get(
                    model, ModelCapability(strengths=[])
                )
                yield (provider.name, model, capability)

    def infer_provider(
        self,
        model: str,
        runtime_provider: Optional[str] = None,
    ) -> Optional[ProviderConfig]:
        """Infer provider from runtime config, model name, or settings."""
        # Runtime provider (from UI / settings API) takes highest precedence.
        if runtime_provider:
            provider = self.get(runtime_provider)
            if provider is not None:
                return provider
            # If the runtime provider is not registered yet (e.g. custom), the
            # caller is responsible for registering it; fall through below.

        # Explicit provider setting takes precedence, but only when it names a
        # registered provider.  Unrecognised values (e.g. the "none" sentinel
        # used to disable LLM access) fall through to model-name inference.
        explicit = os.environ.get("HOMOMICS_LLM_PROVIDER")
        if explicit:
            provider = self.get(explicit)
            if provider is not None:
                return provider
        explicit_setting = getattr(settings, "llm_provider", None)
        if explicit_setting:
            provider = self.get(explicit_setting)
            if provider is not None:
                return provider

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


def reset_provider_registry() -> None:
    """Reset the module-level registry singleton so it is rebuilt on next use."""
    global _registry
    _registry = None


def register_custom_provider(
    base_url: str,
    api_key: str,
    model: str,
    name: str = "custom",
) -> ProviderConfig:
    """Register and return a dynamic custom OpenAI-compatible provider."""
    registry = get_provider_registry()
    config = ProviderConfig(
        name=name,
        display_name="Custom Endpoint",
        base_url=base_url,
        api_key_env="CUSTOM_API_KEY",
        secret_key="CUSTOM_API_KEY",
        default_models=[model],
        explicit_api_key=api_key,
        explicit_base_url=base_url,
    )
    registry.register(config)
    return config
