"""Tests for the LLM provider registry, router, and cost estimation."""


import pytest

from homomics_lab.llm import ProviderRegistry, estimate_cost_usd
from homomics_lab.llm.providers import ProviderConfig
from homomics_lab.llm.router import LLMRouter


class TestProviderRegistry:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        registry.register(
            ProviderConfig(
                name="test",
                display_name="Test",
                base_url="http://localhost",
                api_key_env="TEST_API_KEY",
                secret_key="TEST_API_KEY",
                default_models=["test-model"],
            )
        )
        p = registry.get("test")
        assert p is not None
        assert p.display_name == "Test"

    def test_infer_openai(self):
        registry = ProviderRegistry()
        assert registry.infer_provider("gpt-4o").name == "openai"
        assert registry.infer_provider("gpt-4o-mini").name == "openai"

    def test_infer_domestic(self):
        registry = ProviderRegistry()
        assert registry.infer_provider("deepseek-chat").name == "deepseek"
        assert registry.infer_provider("qwen-plus").name == "qwen"
        assert registry.infer_provider("glm-4").name == "zhipu"
        assert registry.infer_provider("moonshot-v1-8k").name == "moonshot"


class TestCostEstimation:
    def test_known_model(self):
        cost = estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75, rel=1e-6)

    def test_domestic_model(self):
        cost = estimate_cost_usd("deepseek-chat", 1_000_000, 1_000_000)
        assert cost > 0

    def test_unknown_model_defaults(self):
        cost_unknown = estimate_cost_usd("unknown-model", 1_000_000, 1_000_000)
        cost_default = estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000)
        assert cost_unknown == cost_default


class TestLLMRouter:
    def test_select_raises_when_unconfigured(self):
        registry = ProviderRegistry()
        # Wipe out any configured providers by monkeypatching is_configured.
        for p in registry.list():
            p.is_configured = lambda: False
        router = LLMRouter(registry=registry, primary_model="gpt-4o-mini")
        with pytest.raises(RuntimeError):
            router.select()

    def test_select_uses_explicit_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        router = LLMRouter()
        decision = router.select(model="gpt-4o")
        assert decision.model == "gpt-4o"
        assert decision.provider.name == "openai"

    def test_select_prefers_domestic_when_configured(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setenv("HOMOMICS_LLM_MODEL", "deepseek-chat")
        router = LLMRouter()
        decision = router.select()
        assert decision.model == "deepseek-chat"
        assert decision.provider.name == "deepseek"

    def test_list_available_models(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        router = LLMRouter()
        models = router.list_available_models()
        assert any(m["provider"] == "openai" for m in models)

    def test_local_provider_restricts_fallback_to_primary(self):
        from homomics_lab.llm.runtime_config import LLMRuntimeConfig

        registry = ProviderRegistry()
        ollama = registry.get("ollama")
        ollama.explicit_api_key = "dummy"
        ollama.explicit_base_url = "http://localhost:11434/v1"

        runtime = LLMRuntimeConfig(
            provider="ollama",
            model="qwen2.5:1.5b",
            api_key="dummy",
            base_url="http://localhost:11434/v1",
        )
        router = LLMRouter(registry=registry, runtime_config=runtime)
        assert router.primary_model == "qwen2.5:1.5b"
        assert router.fallback_models == ["qwen2.5:1.5b"]

        decision = router.select()
        assert decision.model == "qwen2.5:1.5b"
        assert decision.provider.name == "ollama"

    def test_local_provider_complexity_routing_uses_primary(self):
        from homomics_lab.llm.runtime_config import LLMRuntimeConfig

        registry = ProviderRegistry()
        ollama = registry.get("ollama")
        ollama.explicit_api_key = "dummy"
        ollama.explicit_base_url = "http://localhost:11434/v1"

        runtime = LLMRuntimeConfig(
            provider="ollama",
            model="qwen2.5:1.5b",
            api_key="dummy",
            base_url="http://localhost:11434/v1",
        )
        router = LLMRouter(registry=registry, runtime_config=runtime)
        decision = router.select_by_complexity(intent_type="planning")
        assert decision.model == "qwen2.5:1.5b"
        assert decision.provider.name == "ollama"
