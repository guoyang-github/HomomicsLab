"""Short-term TTL cache for intent classification results.

The cascade intent analyzer is rebuilt for every chat message (one
``TurnRunner`` per ``/api/chat/send``), so an instance-level cache would never
hit. This module provides a small process-wide LRU cache with TTL that lives
at module level and is shared by all analyzer instances.

Cache keys are content-derived (message + classification-relevant context +
intent definitions + classifier/collaborator identity tokens), so entries
never leak across sessions, definition reloads, or differently-configured
analyzers. See ``CascadeIntentAnalyzer._make_cache_key`` for the key layout.
"""

from __future__ import annotations

import copy
import threading
import time
from collections import OrderedDict
from typing import Any, Optional, Tuple

from homomics_lab.agent.intent.models import UserIntent


class IntentResultCache:
    """Bounded LRU cache with per-entry TTL for ``UserIntent`` results.

    - ``maxsize`` bounds memory; least-recently-used entries are evicted first.
    - Entries expire after ``ttl_seconds`` (default 60s).
    - ``get`` returns a deep copy so callers can mutate the intent (e.g. CBKB
      enrichment, downstream metadata edits) without corrupting the cached
      value.
    - ``refs`` are strong references kept alongside the entry to pin the
      identity of key contributors (LLM client, CBKB) whose ``id()`` is part
      of the cache key; pinning prevents ``id()`` reuse while the entry lives.
    """

    def __init__(self, maxsize: int = 256, ttl_seconds: float = 60.0):
        self._maxsize = max(1, maxsize)
        self._ttl = ttl_seconds
        # key -> (expires_at_monotonic, intent, refs)
        self._entries: "OrderedDict[str, Tuple[float, UserIntent, Tuple[Any, ...]]]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def normalize_message(message: str) -> str:
        """Collapse whitespace so trivially-identical messages share a key."""
        return " ".join(message.split())

    def get(self, key: str) -> Optional[UserIntent]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, intent, _refs = entry
            if expires_at <= time.monotonic():
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
        return copy.deepcopy(intent)

    def put(self, key: str, intent: UserIntent, refs: Tuple[Any, ...] = ()) -> None:
        with self._lock:
            now = time.monotonic()
            # Drop expired entries lazily on write.
            expired = [k for k, (exp, _i, _r) in self._entries.items() if exp <= now]
            for k in expired:
                del self._entries[k]
            while len(self._entries) >= self._maxsize:
                self._entries.popitem(last=False)
            # Snapshot the intent so later caller-side mutation does not
            # corrupt the cached value (``get`` returns its own deep copy).
            self._entries[key] = (now + self._ttl, copy.deepcopy(intent), refs)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


_SHARED_INTENT_RESULT_CACHE = IntentResultCache()


def get_shared_intent_result_cache() -> IntentResultCache:
    """Return the process-wide cache shared by all analyzer instances."""
    return _SHARED_INTENT_RESULT_CACHE
