"""LLM routing, fallback, and cost-aware model selection.

The router decides which provider/model to use for a request, supports a primary
→ fallback chain, and can downgrade to a cheaper model when budgets are tight.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.cost_control import BudgetExceeded, get_cost_controller
from homomics_lab.llm.cost import estimate_cost_usd
from homomics_lab.llm.providers import (
    ProviderConfig,
    ProviderRegistry,
    get_provider_registry,
    register_custom_provider,
)
from homomics_lab.llm.runtime_config import DEFAULT_FALLBACK_MODELS, LLMRuntimeConfig


@dataclass
class RouteDecision:
    """Result of an LLM routing decision."""

    provider: ProviderConfig
    model: str
    estimated_input_cost_usd: float = 0.0
    reason: str = "primary"


class LLMRouter:
    """Route LLM requests across providers with fallback and budget awareness."""

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        primary_model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        max_budget_usd: Optional[float] = None,
        runtime_config: Optional[LLMRuntimeConfig] = None,
    ):
        self.registry = registry or get_provider_registry()
        self.runtime_config = runtime_config
        if runtime_config is not None:
            if runtime_config.provider == "custom":
                register_custom_provider(
                    base_url=runtime_config.base_url or "",
                    api_key=runtime_config.api_key or "",
                    model=runtime_config.model or "custom-model",
                )
            elif runtime_config.provider and runtime_config.api_key:
                # Apply runtime API key / base URL overrides to the registry provider.
                provider = self.registry.get(runtime_config.provider)
                if provider is not None:
                    provider.explicit_api_key = runtime_config.api_key
                    if runtime_config.base_url:
                        provider.explicit_base_url = runtime_config.base_url
        self.primary_model = (
            (runtime_config.model if runtime_config else None)
            or primary_model
            or self._default_primary_model()
        )
        self.fallback_models = self._resolve_fallback_models(
            runtime_config=runtime_config,
            fallback_models=fallback_models,
        )
        self.max_budget_usd = max_budget_usd

    def _resolve_fallback_models(
        self,
        runtime_config: Optional[LLMRuntimeConfig],
        fallback_models: Optional[List[str]],
    ) -> List[str]:
        """Resolve fallback model list, honouring runtime config and local providers.

        Local/self-hosted providers (Ollama) only have the models the user has
        pulled.  Falling back to hard-coded cloud model names such as
        ``gpt-4o-mini`` therefore always fails, so we restrict the fallback chain
        to the configured local model unless the user explicitly provided a list
        of local fallback models.
        """
        if runtime_config is not None and runtime_config.fallback_models is not None:
            models = list(runtime_config.fallback_models)
        elif fallback_models is not None:
            models = list(fallback_models)
        else:
            models = self._default_fallback_models()

        if self._is_local_provider(runtime_config):
            # Only fall back within the same local model family.  If the user did
            # not configure an explicit local fallback list, default to the
            # primary model only.
            if not models or set(models) == set(DEFAULT_FALLBACK_MODELS):
                return [self.primary_model]
            # Keep only candidates that are not obviously cloud-only names.
            local_candidates = [
                m for m in models
                if self.registry.infer_provider(m, runtime_provider=self._runtime_provider_name()) is not self.registry.get("openai")
            ]
            if local_candidates:
                return local_candidates
            return [self.primary_model]

        return models

    def _is_local_provider(self, runtime_config: Optional[LLMRuntimeConfig]) -> bool:
        provider = self._runtime_provider_name(runtime_config)
        return provider in ("ollama", "local")

    def _runtime_provider_name(self, runtime_config: Optional[LLMRuntimeConfig] = None) -> Optional[str]:
        return (runtime_config or self.runtime_config).provider if (runtime_config or self.runtime_config) else None

    @staticmethod
    def _default_primary_model() -> str:
        return os.environ.get("HOMOMICS_LLM_MODEL") or getattr(settings, "llm_model", None) or "gpt-4o-mini"

    @staticmethod
    def _default_fallback_models() -> List[str]:
        env = os.environ.get("HOMOMICS_LLM_FALLBACK_MODELS")
        if env:
            return [m.strip() for m in env.split(",") if m.strip()]
        # Default fallback chain: cheap OpenAI -> domestic cheap models -> local.
        return list(DEFAULT_FALLBACK_MODELS)

    def _check_budget(self, estimated_cost: float) -> None:
        """Raise BudgetExceeded if this request would exceed configured caps."""
        controller = get_cost_controller()
        controller.check_request_budget(estimated_cost)
        if self.max_budget_usd is not None:
            controller.check_request_budget(estimated_cost, cap=self.max_budget_usd)

    def select(
        self,
        model: Optional[str] = None,
        prefer_cheap: bool = False,
        expected_input_tokens: int = 1000,
        expected_output_tokens: int = 500,
            skip: Optional[set] = None,
    ) -> RouteDecision:
        """Select the best provider/model for the current request.

        Args:
            model: Explicitly requested model. If provided, try it first.
            prefer_cheap: If True, prefer the cheapest configured model.
            expected_input_tokens: Used for budget estimation.
            expected_output_tokens: Used for budget estimation.
            skip: Set of model names to exclude (used after a failure).
        """
        candidates: List[str] = []
        if model:
            candidates.append(model)
        if prefer_cheap:
            # Sort fallback chain by estimated cost.
            candidates.extend(
                sorted(
                    self.fallback_models,
                    key=lambda m: estimate_cost_usd(m, expected_input_tokens, expected_output_tokens),
                )
            )
        else:
            candidates.append(self.primary_model)
            candidates.extend(self.fallback_models)

        # Deduplicate while preserving order.
        seen = set()
        unique_candidates = []
        for m in candidates:
            if m not in seen and m not in (skip or set()):
                seen.add(m)
                unique_candidates.append(m)

        last_error: Optional[Exception] = None
        runtime_provider = self.runtime_config.provider if self.runtime_config else None
        for candidate in unique_candidates:
            provider = self.registry.infer_provider(candidate, runtime_provider=runtime_provider)
            if provider is None or not provider.is_configured():
                continue
            estimated = estimate_cost_usd(candidate, expected_input_tokens, expected_output_tokens)
            try:
                self._check_budget(estimated)
            except BudgetExceeded as exc:
                last_error = exc
                continue

            reason = "explicit" if candidate == model else ("cheap" if prefer_cheap else "fallback")
            if candidate == self.primary_model and not model:
                reason = "primary"
            return RouteDecision(provider=provider, model=candidate, estimated_input_cost_usd=estimated, reason=reason)

        if last_error:
            raise last_error
        raise RuntimeError(
            "No LLM provider is configured. Set one of: OPENAI_API_KEY, DEEPSEEK_API_KEY, "
            "DASHSCOPE_API_KEY, ZHIPU_API_KEY, MOONSHOT_API_KEY, or OLLAMA_API_KEY."
        )

    def select_by_complexity(
        self,
        intent_type: str = "general",
        input_token_count: int = 1000,
        expected_output_tokens: int = 500,
    ) -> RouteDecision:
        """Pick a model based on task complexity and context size.

        Cheap models are used for simple classification/clarification; strong
        models for planning, interpretation, and code generation. Long contexts
        prefer models with large context windows.
        """
        # Local/self-hosted providers only have the user's pulled models; the
        # hard-coded cloud complexity candidates would all 404.  Fall back to the
        # normal selection, which is constrained to the local model.
        if self._is_local_provider(self.runtime_config):
            return self.select(expected_input_tokens=input_token_count, expected_output_tokens=expected_output_tokens)

        simple_intents = {"greeting", "clarification", "chitchat", "faq", "status"}
        complex_intents = {"planning", "interpretation", "code_generation", "analysis", "debug"}

        if input_token_count > 120_000:
            candidates = ["claude-3-5-sonnet-20241022", "moonshot-v1-128k", "gpt-4o"]
        elif intent_type in simple_intents:
            candidates = ["gpt-4o-mini", "deepseek-chat", "glm-4-flash", "qwen-turbo"]
        elif intent_type in complex_intents:
            candidates = ["gpt-4o", "claude-3-5-sonnet-20241022", "deepseek-reasoner"]
        else:
            candidates = [self.primary_model] + self.fallback_models

        seen = set()
        runtime_provider = self.runtime_config.provider if self.runtime_config else None
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            provider = self.registry.infer_provider(candidate, runtime_provider=runtime_provider)
            if provider is None or not provider.is_configured():
                continue
            estimated = estimate_cost_usd(candidate, input_token_count, expected_output_tokens)
            try:
                self._check_budget(estimated)
            except BudgetExceeded:
                continue
            return RouteDecision(
                provider=provider,
                model=candidate,
                estimated_input_cost_usd=estimated,
                reason=f"complexity:{intent_type}",
            )
        # Fall back to normal selection if complexity candidates fail budget/provider.
        return self.select(expected_input_tokens=input_token_count, expected_output_tokens=expected_output_tokens)

    def list_available_models(self) -> List[Dict[str, str]]:
        """Return all models whose providers are configured."""
        result = []
        for provider in self.registry.list_configured():
            for model in provider.default_models:
                result.append({"provider": provider.name, "model": model, "display_name": provider.display_name})
        return result
