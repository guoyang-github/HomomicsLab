"""Tests for LLM response cache backends."""

import pytest
from fakeredis import FakeAsyncRedis, FakeServer

from homomics_lab.config import Settings
from homomics_lab.llm.cache import (
    LocalLLMResponseCache,
    RedisLLMResponseCache,
    get_llm_response_cache,
)


class TestLocalLLMResponseCache:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_content(self):
        cache = LocalLLMResponseCache(ttl_seconds=60, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        await cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert await cache.get("gpt-4o-mini", messages, 0.3, 100, None) == "world"

    @pytest.mark.asyncio
    async def test_cache_miss_with_different_temperature(self):
        cache = LocalLLMResponseCache(ttl_seconds=60, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        await cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert await cache.get("gpt-4o-mini", messages, 0.5, 100, None) is None

    @pytest.mark.asyncio
    async def test_cache_expires(self):
        cache = LocalLLMResponseCache(ttl_seconds=0, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        await cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert await cache.get("gpt-4o-mini", messages, 0.3, 100, None) is None

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        cache = LocalLLMResponseCache(ttl_seconds=60, max_entries=10)
        messages = [{"role": "user", "content": "hello"}]
        await cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        await cache.clear()
        assert await cache.get("gpt-4o-mini", messages, 0.3, 100, None) is None


class TestRedisLLMResponseCache:
    @pytest.fixture
    def fake_redis(self, monkeypatch):
        """Patch redis.asyncio.Redis.from_url to return a shared FakeAsyncRedis."""
        server = FakeServer()
        server_redis = FakeAsyncRedis(server=server)

        def _from_url(url, **kwargs):
            return FakeAsyncRedis(server=server)

        monkeypatch.setattr("redis.asyncio.Redis.from_url", _from_url)
        return server_redis

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_content(self, fake_redis):
        cache = RedisLLMResponseCache(redis=fake_redis, ttl_seconds=60)
        messages = [{"role": "user", "content": "hello"}]
        await cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert await cache.get("gpt-4o-mini", messages, 0.3, 100, None) == "world"

    @pytest.mark.asyncio
    async def test_cache_miss_with_different_temperature(self, fake_redis):
        cache = RedisLLMResponseCache(redis=fake_redis, ttl_seconds=60)
        messages = [{"role": "user", "content": "hello"}]
        await cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        assert await cache.get("gpt-4o-mini", messages, 0.5, 100, None) is None

    @pytest.mark.asyncio
    async def test_cache_clear(self, fake_redis):
        cache = RedisLLMResponseCache(redis=fake_redis, ttl_seconds=60)
        messages = [{"role": "user", "content": "hello"}]
        await cache.put("gpt-4o-mini", messages, 0.3, 100, None, "world")
        await cache.clear()
        assert await cache.get("gpt-4o-mini", messages, 0.3, 100, None) is None


class TestCacheFactory:
    def test_factory_returns_local_by_default(self):
        settings = Settings(llm_response_cache_enabled=True, llm_response_cache_backend="local")
        cache = get_llm_response_cache(settings)
        assert isinstance(cache, LocalLLMResponseCache)

    def test_factory_returns_none_when_disabled(self):
        settings = Settings(llm_response_cache_enabled=False)
        assert get_llm_response_cache(settings) is None

    def test_factory_returns_redis_when_configured(self, monkeypatch):
        server = FakeServer()
        monkeypatch.setattr(
            "redis.asyncio.Redis.from_url",
            lambda url, **kwargs: FakeAsyncRedis(server=server),
        )
        settings = Settings(
            llm_response_cache_enabled=True,
            llm_response_cache_backend="redis",
            llm_response_cache_redis_url="redis://localhost:6379/1",
        )
        cache = get_llm_response_cache(settings)
        assert isinstance(cache, RedisLLMResponseCache)

    def test_factory_defaults_redis_url_to_redis_url_setting(self, monkeypatch):
        server = FakeServer()
        monkeypatch.setattr(
            "redis.asyncio.Redis.from_url",
            lambda url, **kwargs: FakeAsyncRedis(server=server),
        )
        settings = Settings(
            llm_response_cache_enabled=True,
            llm_response_cache_backend="redis",
            redis_url="redis://custom-redis:6380/2",
        )
        cache = get_llm_response_cache(settings)
        assert isinstance(cache, RedisLLMResponseCache)
        assert settings.llm_response_cache_redis_url == "redis://custom-redis:6380/2"
