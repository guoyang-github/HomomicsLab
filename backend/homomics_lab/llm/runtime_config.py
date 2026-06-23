"""Runtime LLM configuration loaded from encrypted secrets with env fallback.

This module separates *runtime* LLM configuration from the static pydantic
``Settings`` object.  The UI writes configuration into the encrypted secrets
store (namespace ``llm``); the backend reads it here, falls back to environment
variables / ``.env`` when nothing has been persisted, and applies it to the
LLMRouter / LLMClient on the fly.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from homomics_lab.config import settings
from homomics_lab.secrets import get_secrets_manager


logger = logging.getLogger(__name__)


NAMESPACE = "llm"

# Fallback chain used when no explicit fallback list is configured.
DEFAULT_FALLBACK_MODELS = [
    "gpt-4o-mini",
    "deepseek-chat",
    "qwen-turbo",
    "glm-4-flash",
    "llama3.1",
]

# Frontend uses slightly different names for a couple of providers.
_FRONTEND_TO_BACKEND_PROVIDER = {
    "local": "ollama",
}
_BACKEND_TO_FRONTEND_PROVIDER = {
    "ollama": "local",
}


def _normalize_provider(provider: Optional[str]) -> Optional[str]:
    if provider is None:
        return None
    return _FRONTEND_TO_BACKEND_PROVIDER.get(provider, provider)


def is_local_llm_provider(config: Optional[LLMRuntimeConfig] = None) -> bool:
    """Return True when the effective LLM provider is local/self-hosted."""
    if config is None:
        try:
            config = load_llm_runtime_config()
        except Exception:
            return False
    provider = _normalize_provider(getattr(config, "provider", None))
    return provider in ("ollama", "local")


def _frontend_provider(provider: Optional[str]) -> Optional[str]:
    if provider is None:
        return None
    return _BACKEND_TO_FRONTEND_PROVIDER.get(provider, provider)


def _split_fallback_models(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [m.strip() for m in value.split(",") if m.strip()]


def mask_key(key: Optional[str]) -> Optional[str]:
    """Return a masked representation of an API key for display purposes."""
    if not key:
        return None
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


@dataclass
class LLMRuntimeConfig:
    """Effective LLM configuration used by the router and client."""

    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_models: List[str] = None  # type: ignore[assignment]
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 4096

    def __post_init__(self):
        if self.fallback_models is None:
            self.fallback_models = list(DEFAULT_FALLBACK_MODELS)

    @property
    def is_configured(self) -> bool:
        """True when a model and a usable provider are set."""
        if not self.model or not self.provider:
            return False
        if self.provider == "custom":
            return bool(self.base_url and self.api_key)
        return True

    def to_frontend_dict(self) -> dict:
        """Serialize for the frontend; never expose the raw API key."""
        return {
            "provider": _frontend_provider(self.provider),
            "model": self.model,
            "fallback_models": self.fallback_models,
            "base_url": self.base_url,
            "api_key": mask_key(self.api_key),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


def _safe_get(mgr, key: str, namespace: str = NAMESPACE) -> Optional[str]:
    """Read a secret, treating decryption errors as missing values."""
    try:
        return mgr.get(key, namespace=namespace)
    except Exception as exc:
        logger.warning("Failed to decrypt LLM runtime secret '%s': %s", key, exc)
        return None


def load_llm_runtime_config() -> LLMRuntimeConfig:
    """Load effective LLM config from secrets, falling back to env/settings."""
    mgr = get_secrets_manager()

    provider = (
        _safe_get(mgr, "provider")
        or settings.llm_provider
        or os.environ.get("HOMOMICS_LLM_PROVIDER")
    )
    provider = _normalize_provider(provider)

    model = (
        _safe_get(mgr, "model")
        or settings.llm_model
        or os.environ.get("HOMOMICS_LLM_MODEL")
    )

    fallback_raw = (
        _safe_get(mgr, "fallback_models")
        or settings.llm_fallback_models
        or os.environ.get("HOMOMICS_LLM_FALLBACK_MODELS")
    )
    fallback_models = _split_fallback_models(fallback_raw) or list(DEFAULT_FALLBACK_MODELS)

    # Local/self-hosted providers do not have cloud-only fallback models such as
    # gpt-4o-mini.  Default the fallback chain to the configured local model so
    # the router never tries to call a model that does not exist locally.
    if provider in ("ollama", "local") and set(fallback_models) == set(DEFAULT_FALLBACK_MODELS):
        fallback_models = [model] if model else []

    base_url = _safe_get(mgr, "base_url")
    api_key = _safe_get(mgr, "api_key")

    # Ollama's OpenAI-compatible endpoint lives under /v1.
    if provider == "ollama" and base_url and not base_url.rstrip("/").endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    temperature = 0.2
    max_tokens = 4096
    temp_raw = _safe_get(mgr, "temperature")
    if temp_raw is not None:
        try:
            temperature = float(temp_raw)
        except ValueError:
            pass
    tokens_raw = _safe_get(mgr, "max_tokens")
    if tokens_raw is not None:
        try:
            max_tokens = int(tokens_raw)
        except ValueError:
            pass

    # If the provider is known and the user did not supply a base URL or key,
    # fall back to the provider registry defaults / environment variables.
    if provider and provider != "custom":
        from homomics_lab.llm.providers import get_provider_registry

        registry = get_provider_registry()
        pc = registry.get(provider)
        if pc is not None:
            if not base_url:
                base_url = pc.resolved_base_url
            if not api_key:
                api_key = os.environ.get(pc.api_key_env)
                if not api_key:
                    api_key = _safe_get(mgr, pc.secret_key, namespace=pc.secret_namespace)

    return LLMRuntimeConfig(
        provider=provider,
        model=model,
        fallback_models=fallback_models,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def save_llm_runtime_config(config: LLMRuntimeConfig) -> None:
    """Persist runtime LLM config to the encrypted secrets store."""
    mgr = get_secrets_manager()
    provider = _normalize_provider(config.provider)

    if provider:
        mgr.set("provider", provider, namespace=NAMESPACE)
    else:
        mgr.delete("provider", namespace=NAMESPACE)

    if config.model:
        mgr.set("model", config.model, namespace=NAMESPACE)
    else:
        mgr.delete("model", namespace=NAMESPACE)

    if config.fallback_models:
        mgr.set("fallback_models", ",".join(config.fallback_models), namespace=NAMESPACE)
    else:
        mgr.delete("fallback_models", namespace=NAMESPACE)

    if config.base_url:
        mgr.set("base_url", config.base_url, namespace=NAMESPACE)
    else:
        mgr.delete("base_url", namespace=NAMESPACE)

    if config.api_key:
        mgr.set("api_key", config.api_key, namespace=NAMESPACE)
    else:
        mgr.delete("api_key", namespace=NAMESPACE)

    mgr.set("temperature", str(config.temperature), namespace=NAMESPACE)
    mgr.set("max_tokens", str(config.max_tokens), namespace=NAMESPACE)
