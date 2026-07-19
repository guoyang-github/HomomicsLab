"""Capability-based LLM routing tests."""

from unittest.mock import MagicMock

import pytest

from homomics_lab.llm.providers import (
    ModelCapability,
    ProviderConfig,
    ProviderRegistry,
)
from homomics_lab.llm.router import LLMRouter


def _make_registry(configured_models):
    """Build a tiny registry with the given configured (provider, model, cap) tuples."""
    registry = ProviderRegistry()
    registry._providers = {}
    by_provider = {}
    for provider_name, model, cap in configured_models:
        by_provider.setdefault(provider_name, []).append((model, cap))

    for provider_name, items in by_provider.items():
        models = [m for m, _ in items]
        caps = {m: cap for m, cap in items}
        config = ProviderConfig(
            name=provider_name,
            display_name=provider_name.capitalize(),
            base_url="https://example.com/v1",
            api_key_env=f"{provider_name.upper()}_API_KEY",
            secret_key=f"{provider_name.upper()}_API_KEY",
            default_models=models,
            explicit_api_key="sk-test",
            model_capabilities=caps,
        )
        registry.register(config)
    return registry


@pytest.fixture
def mock_registry():
    return _make_registry([
        ("openai", "gpt-4o", ModelCapability(
            context_window=128_000,
            cost_rank=3,
            supports_tool_calling=True,
            strengths=["analysis", "coding", "reasoning"],
        )),
        ("openai", "gpt-4o-mini", ModelCapability(
            context_window=128_000,
            cost_rank=1,
            supports_tool_calling=True,
            strengths=["classification", "cheap"],
        )),
        ("deepseek", "deepseek-reasoner", ModelCapability(
            cost_rank=2,
            supports_reasoning=True,
            strengths=["reasoning", "coding"],
        )),
        ("deepseek", "deepseek-chat", ModelCapability(
            cost_rank=1,
            strengths=["classification", "cheap"],
        )),
        ("anthropic", "claude-3-5-sonnet-20241022", ModelCapability(
            context_window=200_000,
            cost_rank=3,
            strengths=["analysis", "coding", "long_context"],
        )),
        ("moonshot", "moonshot-v1-128k", ModelCapability(
            context_window=128_000,
            cost_rank=2,
            strengths=["long_context", "analysis"],
        )),
        ("ollama", "llama3.1", ModelCapability()),
    ])


class TestListModelsWithCapabilities:
    def test_returns_capabilities(self, mock_registry):
        rows = list(mock_registry.list_models_with_capabilities())
        models = {model for _, model, _ in rows}
        assert "gpt-4o" in models
        assert "deepseek-reasoner" in models

        for provider, model, cap in rows:
            if model == "gpt-4o":
                assert cap.cost_rank == 3
                assert "analysis" in cap.strengths
            if model == "gpt-4o-mini":
                assert cap.cost_rank == 1
                assert "classification" in cap.strengths


class TestCapabilityRouting:
    def test_simple_intent_prefers_cheap_classification_model(self, mock_registry):
        router = LLMRouter(registry=mock_registry)
        decision = router.select_by_complexity(intent_type="greeting")
        assert decision.model in {"gpt-4o-mini", "deepseek-chat"}

    def test_complex_intent_prefers_reasoning_or_coding_model(self, mock_registry):
        router = LLMRouter(registry=mock_registry)
        decision = router.select_by_complexity(intent_type="planning")
        assert decision.model in {"gpt-4o", "deepseek-reasoner", "claude-3-5-sonnet-20241022"}

    def test_long_context_prefers_large_context_window(self, mock_registry):
        router = LLMRouter(registry=mock_registry)
        decision = router.select_by_complexity(
            intent_type="general",
            input_token_count=150_000,
        )
        assert decision.model in {
            "claude-3-5-sonnet-20241022",
            "moonshot-v1-128k",
            "gpt-4o",
            "gpt-4o-mini",
        }

    def test_unknown_model_names_use_capability_catalog(self, mock_registry):
        """A model not in original hard-coded lists is routed by its capability tags."""
        registry = _make_registry([
            ("openai", "gpt-4o-mini", ModelCapability(
                cost_rank=1,
                strengths=["classification", "cheap"],
            )),
            ("openai", "o3-mini", ModelCapability(
                cost_rank=2,
                supports_reasoning=True,
                strengths=["reasoning", "coding"],
            )),
        ])
        router = LLMRouter(registry=registry)
        decision = router.select_by_complexity(intent_type="code_generation")
        assert decision.model == "o3-mini"

    def test_complexity_routing_disabled_falls_back_to_select(self, monkeypatch, mock_registry):
        monkeypatch.setattr("homomics_lab.llm.router.LLM_COMPLEXITY_ROUTING_ENABLED", False)
        router = LLMRouter(registry=mock_registry, primary_model="gpt-4o")
        decision = router.select_by_complexity(intent_type="greeting")
        assert decision.model == "gpt-4o"

    def test_local_provider_ignores_complexity_routing(self, mock_registry):
        runtime_config = MagicMock()
        runtime_config.provider = "ollama"
        runtime_config.model = "llama3.1"
        runtime_config.fallback_models = None
        runtime_config.api_key = None
        runtime_config.base_url = None
        router = LLMRouter(registry=mock_registry, runtime_config=runtime_config)
        decision = router.select_by_complexity(intent_type="greeting")
        assert decision.model == "llama3.1"
