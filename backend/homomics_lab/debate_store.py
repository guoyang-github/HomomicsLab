"""Persistent, async-safe storage for active HITL debates.

The debate state was previously held in a module-level ``dict`` in
``api/chat.py``.  This module replaces it with a small JSON-backed store
so that debates survive API restarts and concurrent requests are safe.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from homomics_lab.config import settings


class DebateStore:
    """JSON file store for per-session debate payloads.

    Each debate is stored as ``{store_dir}/{session_id}.json`` and all
    reads/writes are serialized with an asyncio lock so the store can be
    used safely as a global singleton across concurrent requests.
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._store_dir = store_dir or settings.data_dir / "debates"
        self._lock = asyncio.Lock()

    def _path(self, session_id: str) -> Path:
        return self._store_dir / f"{session_id}.json"

    async def save(self, session_id: str, debate: Dict[str, Any]) -> None:
        """Persist a debate payload for the given session."""
        async with self._lock:
            self._store_dir.mkdir(parents=True, exist_ok=True)
            self._path(session_id).write_text(
                json.dumps(debate, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load a persisted debate payload, if any."""
        async with self._lock:
            path = self._path(session_id)
            if not path.exists():
                return None
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None

    async def delete(self, session_id: str) -> None:
        """Remove the persisted debate for a session."""
        async with self._lock:
            path = self._path(session_id)
            if path.exists():
                path.unlink()
