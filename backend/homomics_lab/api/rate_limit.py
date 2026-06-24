"""Request rate limiting for HomomicsLab.

Rate limiting is opt-in via ``HOMOMICS_RATE_LIMIT_ENABLED``. The default
implementation is an in-memory sliding window suitable for a single-process or
low-traffic deployment. For multi-replica production deployments, set
``HOMOMICS_RATE_LIMIT_BACKEND=redis`` and configure ``HOMOMICS_REDIS_URL``.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Dict, Optional, Union

from fastapi import HTTPException, Request, status

from homomics_lab.config import settings


class InMemoryRateLimiter:
    """Sliding-window rate limiter keyed by client identity."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 60):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._windows: Dict[str, deque] = {}

    def _client_ip(self, request: Request) -> str:
        """Return the client IP, optionally trusting ``X-Forwarded-For``."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded and settings.rate_limit_trust_proxy:
            # Use the rightmost address as the most trustworthy client IP when
            # the app is behind known proxies.
            return forwarded.split(",")[-1].strip()
        return request.client.host if request.client else "unknown"

    def _key(self, request: Request) -> str:
        """Derive a limit key from API key or client IP."""
        api_key = request.headers.get("X-API-Key") or ""
        if api_key:
            return f"key:{api_key}"
        return f"ip:{self._client_ip(request)}"

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window = self._windows.setdefault(key, deque())

        # Drop timestamps outside the window.
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            return False

        window.append(now)
        return True

    async def check_request(self, request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        key = self._key(request)
        if not self.is_allowed(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
            )


class RedisRateLimiter:
    """Redis-backed rate limiter using atomic INCR/EXPIRE sliding windows."""

    def __init__(
        self,
        window_seconds: int = 60,
        max_requests: int = 60,
        redis_url: Optional[str] = None,
        redis_client=None,
    ):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._redis_url = redis_url or settings.rate_limit_redis_url or settings.redis_url
        self._client = redis_client

    @property
    def redis(self):
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded and settings.rate_limit_trust_proxy:
            return forwarded.split(",")[-1].strip()
        return request.client.host if request.client else "unknown"

    def _key(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key") or ""
        if api_key:
            return f"rate:key:{api_key}"
        return f"rate:ip:{self._client_ip(request)}"

    async def is_allowed(self, key: str) -> bool:
        # Use an atomic pipeline to increment the request counter and refresh
        # the key TTL. This keeps the implementation compatible with fakeredis
        # (used in tests) while still being safe for concurrent Redis clients.
        async with self.redis.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, self.window_seconds)
            results = await pipe.execute()
        count = results[0]
        return count <= self.max_requests

    async def check_request(self, request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        key = self._key(request)
        if not await self.is_allowed(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
            )


RateLimiter = Union[InMemoryRateLimiter, RedisRateLimiter]


def get_rate_limiter() -> RateLimiter:
    """Factory returning the configured rate limiter backend."""
    if settings.rate_limit_backend == "redis":
        return RedisRateLimiter(
            window_seconds=60,
            max_requests=settings.rate_limit_requests_per_minute,
        )
    return InMemoryRateLimiter(
        window_seconds=60,
        max_requests=settings.rate_limit_requests_per_minute,
    )


# Global limiter instance. Use ``update_limiter_config()`` to refresh from settings.
_rate_limiter: RateLimiter = get_rate_limiter()


def update_limiter_config() -> None:
    """Synchronize limiter configuration with settings, swapping backend if needed."""
    global _rate_limiter
    backend = settings.rate_limit_backend
    current_backend = "redis" if isinstance(_rate_limiter, RedisRateLimiter) else "memory"
    if backend != current_backend:
        _rate_limiter = get_rate_limiter()
    else:
        _rate_limiter.max_requests = settings.rate_limit_requests_per_minute


async def rate_limit_dependency(request: Request = None) -> None:  # type: ignore[assignment]
    """FastAPI dependency that applies rate limiting to a route.

    WebSocket connections are skipped because they are long-lived and have
    their own backpressure logic. When ``request`` is not provided (e.g. for
    WebSocket routes) the dependency returns immediately.
    """
    if request is None or request.scope.get("type") == "websocket":
        return
    await _rate_limiter.check_request(request)


def get_rate_limit_status(key: Optional[str] = None) -> Dict[str, int]:
    """Return current rate-limit state for a key (mostly for tests/health)."""
    if isinstance(_rate_limiter, RedisRateLimiter):
        # Redis state is opaque without scanning all window keys; return config.
        return {
            "window_seconds": _rate_limiter.window_seconds,
            "max_requests": _rate_limiter.max_requests,
            "remaining": -1,
            "used": -1,
        }

    now = time.time()
    window = _rate_limiter._windows.get(key, deque()) if key else deque()
    valid = [t for t in window if t >= now - _rate_limiter.window_seconds]
    return {
        "window_seconds": _rate_limiter.window_seconds,
        "max_requests": _rate_limiter.max_requests,
        "remaining": max(0, _rate_limiter.max_requests - len(valid)),
        "used": len(valid),
    }
