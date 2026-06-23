"""Deterministic response cache for LLM calls.

Caches complete response strings keyed by a hash of the request parameters.
Useful for reducing repeated calls to identical prompts (e.g. episodic summary
refresh, intent classification in stable sessions).

Backends:
  - LocalLLMResponseCache: in-memory cache with optional JSON disk persistence.
  - RedisLLMResponseCache: shared Redis cache using ``redis.asyncio``.
"""

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _make_key(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    response_format: Optional[Dict[str, str]] = None,
) -> str:
    """Stable hash key for a chat-completion request."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": response_format,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class BaseLLMResponseCache(ABC):
    """Abstract base for LLM response caches."""

    @abstractmethod
    async def get(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Return cached response if present and not expired."""
        ...

    @abstractmethod
    async def put(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]],
        content: str,
    ) -> None:
        """Store a response in the cache."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached entries."""
        ...


class LocalLLMResponseCache(BaseLLMResponseCache):
    """In-memory response cache with TTL and size cap."""

    def __init__(
        self,
        ttl_seconds: float = 3600.0,
        max_entries: int = 1000,
        persist_dir: Optional[Path] = None,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.persist_dir = persist_dir
        self._cache: Dict[str, Dict[str, Any]] = {}
        if self.persist_dir:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    async def get(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Return cached response if present and not expired."""
        key = _make_key(model, messages, temperature, max_tokens, response_format)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["ts"] > self.ttl_seconds:
            del self._cache[key]
            return None
        logger.debug("LLM cache hit for model %s", model)
        return entry["content"]

    async def put(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]],
        content: str,
    ) -> None:
        """Store a response in the cache."""
        if len(self._cache) >= self.max_entries:
            # Evict oldest by insertion timestamp
            oldest = min(self._cache, key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest]

        key = _make_key(model, messages, temperature, max_tokens, response_format)
        self._cache[key] = {"content": content, "ts": time.time()}
        if self.persist_dir:
            self._persist()

    async def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        if self.persist_dir:
            self._persist()

    def _persist(self) -> None:
        """Save the cache to disk (best-effort)."""
        if not self.persist_dir:
            return
        path = self.persist_dir / "llm_cache.json"
        try:
            path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist LLM cache: %s", exc)

    def _load(self) -> None:
        """Load the cache from disk (best-effort)."""
        path = self.persist_dir / "llm_cache.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            now = time.time()
            self._cache = {
                k: v for k, v in data.items() if now - v.get("ts", 0) <= self.ttl_seconds
            }
        except Exception as exc:
            logger.warning("Failed to load LLM cache: %s", exc)


class RedisLLMResponseCache(BaseLLMResponseCache):
    """Shared Redis-backed LLM response cache."""

    KEY_PREFIX = "llm:cache:"

    def __init__(
        self,
        redis,
        ttl_seconds: float = 3600.0,
        max_entries: int = 1000,
    ):
        self._redis = redis
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries

    def _redis_key(self, key: str) -> str:
        return f"{self.KEY_PREFIX}{key}"

    async def get(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Return cached response if present and not expired."""
        key = self._redis_key(_make_key(model, messages, temperature, max_tokens, response_format))
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            # Redis TTL is the primary expiration mechanism; guard against clock skew.
            if time.time() - data.get("ts", 0) > self.ttl_seconds:
                await self._redis.delete(key)
                return None
            logger.debug("LLM cache hit for model %s", model)
            return data["content"]
        except Exception as exc:
            logger.warning("Failed to decode LLM cache entry: %s", exc)
            return None

    async def put(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]],
        content: str,
    ) -> None:
        """Store a response in the cache."""
        key = self._redis_key(_make_key(model, messages, temperature, max_tokens, response_format))
        payload = json.dumps({"content": content, "ts": time.time()}, ensure_ascii=False)
        ttl = max(1, int(self.ttl_seconds))
        await self._redis.set(key, payload, ex=ttl)

    async def clear(self) -> None:
        """Clear all cached entries."""
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match=f"{self.KEY_PREFIX}*", count=100
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break

    async def close(self) -> None:
        """Close the Redis connection if it has a close/aclose method."""
        close = getattr(self._redis, "aclose", None) or getattr(self._redis, "close", None)
        if close is not None:
            await close()


class DisabledLLMResponseCache(BaseLLMResponseCache):
    """No-op cache returned when caching is disabled.

    Kept for explicitness; callers typically use ``None`` instead.
    """

    async def get(self, *args, **kwargs) -> Optional[str]:  # noqa: ARG002
        return None

    async def put(self, *args, **kwargs) -> None:  # noqa: ARG002
        return None

    async def clear(self) -> None:
        return None


# Backward-compatible alias for existing imports/tests.
LLMResponseCache = LocalLLMResponseCache


def get_llm_response_cache(settings) -> Optional[BaseLLMResponseCache]:
    """Factory that builds the configured LLM response cache backend."""
    if not settings.llm_response_cache_enabled:
        return None

    if settings.llm_response_cache_backend == "redis":
        from redis.asyncio import Redis

        redis_url = settings.llm_response_cache_redis_url or settings.redis_url
        redis = Redis.from_url(redis_url)
        return RedisLLMResponseCache(
            redis=redis,
            ttl_seconds=settings.llm_response_cache_ttl_seconds,
            max_entries=settings.llm_response_cache_max_entries,
        )

    return LocalLLMResponseCache(
        ttl_seconds=settings.llm_response_cache_ttl_seconds,
        max_entries=settings.llm_response_cache_max_entries,
        persist_dir=settings.llm_response_cache_dir,
    )
