"""Simple request rate limiting for HomomicsLab.

Rate limiting is opt-in via ``HOMOMICS_RATE_LIMIT_ENABLED``. The default
implementation is an in-memory sliding window suitable for a single-process or
low-traffic deployment. For multi-replica production deployments, replace this
with a Redis-backed limiter.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status

from homomics_lab.config import settings


class InMemoryRateLimiter:
    """Sliding-window rate limiter keyed by client identity."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 60):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._windows: Dict[str, deque] = {}

    def _key(self, request: Request) -> str:
        """Derive a limit key from API key or client IP."""
        api_key = request.headers.get("X-API-Key") or ""
        if api_key:
            return f"key:{api_key}"
        forwarded = request.headers.get("X-Forwarded-For")
        client = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else "unknown"
        return f"ip:{client}"

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

    def check_request(self, request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        key = self._key(request)
        if not self.is_allowed(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
            )


# Global limiter instance.
_rate_limiter = InMemoryRateLimiter(
    window_seconds=60,
    max_requests=settings.rate_limit_requests_per_minute,
)


def update_limiter_config() -> None:
    """Synchronize limiter configuration with settings."""
    _rate_limiter.max_requests = settings.rate_limit_requests_per_minute


def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency that applies rate limiting to a route."""
    _rate_limiter.check_request(request)


def get_rate_limit_status(key: Optional[str] = None) -> Dict[str, int]:
    """Return current rate-limit state for a key (mostly for tests/health)."""
    now = time.time()
    window = _rate_limiter._windows.get(key, deque()) if key else deque()
    valid = [t for t in window if t >= now - _rate_limiter.window_seconds]
    return {
        "window_seconds": _rate_limiter.window_seconds,
        "max_requests": _rate_limiter.max_requests,
        "remaining": max(0, _rate_limiter.max_requests - len(valid)),
        "used": len(valid),
    }
