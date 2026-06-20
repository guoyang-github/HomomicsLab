"""Tests for LLMClient cache, streaming, fallback, and complexity routing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homomics_lab.llm.cache import LLMResponseCache
from homomics_lab.llm.router import LLMRouter
from homomics_lab.llm_client import LLMClient


class TestLLMResponseCache:
    def test_cache_hit_returns_same_content(self):
        cache = LLMResponseCache(ttl_seconds=60, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert cache.get("gpt-4o-mini", messages, 0.3, 100, None) == "world"

    def test_cache_miss_with_different_temperature(self):
        cache = LLMResponseCache(ttl_seconds=60, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert cache.get("gpt-4o-mini", messages, 0.5, 100, None) is None

    def test_cache_expires(self):
        cache = LLMResponseCache(ttl_seconds=0, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert cache.get("gpt-4o-mini", messages, 0.3, 100, None) is None


class TestLLMClientCacheAndFallback:
    @pytest.mark.asyncio
    async def test_cache_avoids_api_call(self, monkeypatch):
        cache = LLMResponseCache(ttl_seconds=60, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4o-mini", messages, 0.3, 100, None, "cached")

        client = LLMClient(cache=cache)
        with patch.object(client, "_get_client") as mock_get_client:
            result = await client.chat_completion(messages=messages, max_tokens=100)
        assert result == "cached"
        mock_get_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self, monkeypatch):
        import asyncio

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        client = LLMClient(model="gpt-4o-mini")

        call_count = 0

        async def fake_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError()
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = "fallback ok"
            response.usage = None
            return response

        def make_client(provider):
            c = MagicMock()
            c.chat.completions.create = AsyncMock(side_effect=fake_create)
            return c

        with patch.object(client, "_get_client", side_effect=make_client):
            result = await client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            )
        assert result == "fallback ok"


class TestLLMClientStreaming:
    @pytest.mark.asyncio
    async def test_stream_returns_tokens(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        client = LLMClient(model="gpt-4o-mini")

        async def fake_stream(*args, **kwargs):
            for token in ["Hello", " ", "world"]:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = token
                yield chunk

        def make_client(provider):
            c = MagicMock()
            c.chat.completions.create = AsyncMock(return_value=fake_stream())
            return c

        with patch.object(client, "_get_client", side_effect=make_client):
            tokens = []
            async for token in client.chat_completion_stream(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            ):
                tokens.append(token)
        assert "".join(tokens) == "Hello world"


class TestLLMRouterComplexity:
    def test_select_by_complexity_simple(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        router = LLMRouter()
        decision = router.select_by_complexity(intent_type="greeting")
        assert decision.model in {"gpt-4o-mini", "deepseek-chat", "glm-4-flash", "qwen-turbo"}

    def test_select_by_complexity_complex(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        router = LLMRouter()
        decision = router.select_by_complexity(intent_type="planning")
        assert decision.model in {"gpt-4o", "claude-3-5-sonnet-20241022", "deepseek-reasoner"}

    def test_select_skip_excludes_failed_models(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        router = LLMRouter()
        decision = router.select(skip={"gpt-4o-mini"})
        assert decision.model != "gpt-4o-mini"
