"""Deterministic response cache for LLM calls.

Caches complete response strings keyed by a hash of the request parameters.
Useful for reducing repeated calls to identical prompts (e.g. episodic summary
refresh, intent classification in stable sessions).
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMResponseCache:
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

    @staticmethod
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

    def get(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Return cached response if present and not expired."""
        key = self._make_key(model, messages, temperature, max_tokens, response_format)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["ts"] > self.ttl_seconds:
            del self._cache[key]
            return None
        logger.debug("LLM cache hit for model %s", model)
        return entry["content"]

    def put(
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

        key = self._make_key(model, messages, temperature, max_tokens, response_format)
        self._cache[key] = {"content": content, "ts": time.time()}
        if self.persist_dir:
            self._persist()

    def clear(self) -> None:
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
