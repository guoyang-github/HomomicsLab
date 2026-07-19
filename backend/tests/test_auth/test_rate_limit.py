"""Tests for in-memory and Redis-backed rate limiters."""

import pytest
from starlette.requests import Request

from homomics_lab.api import rate_limit as rate_limit_module
from homomics_lab.api.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    get_rate_limiter,
    update_limiter_config,
)
from homomics_lab.config import settings


def _make_request(headers=None, client_host="127.0.0.1"):
    header_list = []
    if headers:
        for name, value in headers.items():
            header_list.append((name.lower().encode(), str(value).encode()))
    scope = {
        "type": "http",
        "headers": header_list,
        "client": (client_host, 12345),
    }
    return Request(scope)


class TestInMemoryRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        limiter = InMemoryRateLimiter(window_seconds=60, max_requests=3)
        req = _make_request()

        for _ in range(3):
            await limiter.check_request(req)

        with pytest.raises(Exception) as exc_info:
            await limiter.check_request(req)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_disabled_limiter_bypasses(self, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_enabled", False)
        limiter = InMemoryRateLimiter(window_seconds=60, max_requests=1)
        req = _make_request()

        for _ in range(5):
            await limiter.check_request(req)

    @pytest.mark.asyncio
    async def test_ignores_x_forwarded_for_when_trust_proxy_false(self, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr("homomics_lab.api.rate_limit.RATE_LIMIT_TRUST_PROXY", False)
        limiter = InMemoryRateLimiter(window_seconds=60, max_requests=1)

        req1 = _make_request(headers={"X-Forwarded-For": "10.0.0.1"})
        await limiter.check_request(req1)

        req2 = _make_request(headers={"X-Forwarded-For": "10.0.0.1"})
        with pytest.raises(Exception) as exc_info:
            await limiter.check_request(req2)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_uses_x_forwarded_for_when_trust_proxy_true(self, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr("homomics_lab.api.rate_limit.RATE_LIMIT_TRUST_PROXY", True)
        limiter = InMemoryRateLimiter(window_seconds=60, max_requests=1)

        req1 = _make_request(headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"})
        await limiter.check_request(req1)

        req2 = _make_request(headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"})
        with pytest.raises(Exception) as exc_info:
            await limiter.check_request(req2)
        assert exc_info.value.status_code == 429


class TestRedisRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self, monkeypatch):
        try:
            import fakeredis
        except ImportError:  # pragma: no cover
            pytest.skip("fakeredis not installed")

        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        fake_redis = fakeredis.aioredis.FakeRedis()
        limiter = RedisRateLimiter(
            window_seconds=60,
            max_requests=3,
            redis_client=fake_redis,
        )
        req = _make_request()

        for _ in range(3):
            await limiter.check_request(req)

        with pytest.raises(Exception) as exc_info:
            await limiter.check_request(req)
        assert exc_info.value.status_code == 429

        await fake_redis.aclose()

    @pytest.mark.asyncio
    async def test_disabled_limiter_bypasses(self, monkeypatch):
        try:
            import fakeredis
        except ImportError:  # pragma: no cover
            pytest.skip("fakeredis not installed")

        monkeypatch.setattr(settings, "rate_limit_enabled", False)
        fake_redis = fakeredis.aioredis.FakeRedis()
        limiter = RedisRateLimiter(
            window_seconds=60,
            max_requests=1,
            redis_client=fake_redis,
        )
        req = _make_request()

        for _ in range(5):
            await limiter.check_request(req)

        await fake_redis.aclose()

    @pytest.mark.asyncio
    async def test_x_forwarded_for_handling(self, monkeypatch):
        try:
            import fakeredis
        except ImportError:  # pragma: no cover
            pytest.skip("fakeredis not installed")

        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr("homomics_lab.api.rate_limit.RATE_LIMIT_TRUST_PROXY", True)
        fake_redis = fakeredis.aioredis.FakeRedis()
        limiter = RedisRateLimiter(
            window_seconds=60,
            max_requests=1,
            redis_client=fake_redis,
        )

        req1 = _make_request(headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
        await limiter.check_request(req1)

        req2 = _make_request(headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
        with pytest.raises(Exception) as exc_info:
            await limiter.check_request(req2)
        assert exc_info.value.status_code == 429

        await fake_redis.aclose()


class TestRateLimiterFactory:
    def test_factory_returns_in_memory_by_default(self):
        limiter = get_rate_limiter()
        assert isinstance(limiter, InMemoryRateLimiter)

    def test_update_limiter_config_keeps_memory_backend(self, monkeypatch):
        # The backend is fixed to in-memory; config sync only re-applies the
        # request budget.
        monkeypatch.setattr(rate_limit_module._rate_limiter, "max_requests", 5)
        update_limiter_config()
        assert isinstance(rate_limit_module._rate_limiter, InMemoryRateLimiter)
        assert rate_limit_module._rate_limiter.max_requests == 60
