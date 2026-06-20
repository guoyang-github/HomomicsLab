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
from homomics_lab.llm.providers import ProviderConfig, ProviderRegistry, get_provider_registry


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
    ):
        self.registry = registry or get_provider_registry()
        self.primary_model = primary_model or self._default_primary_model()
        self.fallback_models = fallback_models or self._default_fallback_models()
        self.max_budget_usd = max_budget_usd

    @staticmethod
    def _default_primary_model() -> str:
        return os.environ.get("HOMOMICS_LLM_MODEL") or getattr(settings, "llm_model", None) or "gpt-4o-mini"

    @staticmethod
    def _default_fallback_models() -> List[str]:
        env = os.environ.get("HOMOMICS_LLM_FALLBACK_MODELS")
        if env:
            return [m.strip() for m in env.split(",") if m.strip()]
        # Default fallback chain: cheap OpenAI -> domestic cheap models -> local.
        return [
            "gpt-4o-mini",
            "deepseek-chat",
            "qwen-turbo",
            "glm-4-flash",
            "llama3.1",
        ]

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
        for candidate in unique_candidates:
            provider = self.registry.infer_provider(candidate)
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
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            provider = self.registry.infer_provider(candidate)
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
