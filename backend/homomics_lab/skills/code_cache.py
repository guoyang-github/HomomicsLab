"""CodeAct cache — reuse previously generated code for similar tasks.

The cache is keyed by a deterministic hash of the task, language, and retrieval
context. This avoids paying LLM costs twice for identical or near-identical
requests and allows transient skills to be hit before regeneration.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


class CodeActCache:
    """File-backed cache for generated CodeAct code snippets."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path("./data/codeact_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(
        self,
        task: str,
        language: str,
        context: Optional[Dict[str, Any]] = None,
        retrieval_context: Optional[Any] = None,
    ) -> str:
        """Build a deterministic cache key."""
        parts = [task.strip().lower(), language.lower()]
        if context:
            # Only stable, serializable fields contribute to the key.
            stable_context = {k: v for k, v in context.items() if isinstance(v, (str, int, float, bool, list, dict))}
            parts.append(json.dumps(stable_context, sort_keys=True, ensure_ascii=False))
        if retrieval_context is not None:
            try:
                ctx_dict = retrieval_context.to_prompt_context()
                # Drop volatile scores and keep semantic identities.
                identity = {
                    "intent_type": ctx_dict.get("intent_type"),
                    "skills": [s["id"] for s in ctx_dict.get("skills", [])],
                    "tools": [t["name"] for t in ctx_dict.get("tools", [])],
                    "data_sources": [d["id"] for d in ctx_dict.get("data_sources", [])],
                }
                parts.append(json.dumps(identity, sort_keys=True, ensure_ascii=False))
            except Exception:
                pass
        payload = "|".join(parts).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _cache_path(self, key: str) -> Path:
        """Spread keys across subdirectories to avoid huge flat directories."""
        return self.cache_dir / key[:2] / key[2:4] / f"{key}.json"

    def get(
        self,
        task: str,
        language: str,
        context: Optional[Dict[str, Any]] = None,
        retrieval_context: Optional[Any] = None,
    ) -> Optional[str]:
        """Return cached code if present."""
        key = self._make_key(task, language, context, retrieval_context)
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("code")
        except Exception:
            return None

    def put(
        self,
        task: str,
        language: str,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        retrieval_context: Optional[Any] = None,
    ) -> None:
        """Store generated code in the cache."""
        key = self._make_key(task, language, context, retrieval_context)
        path = self._cache_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "key": key,
            "task": task,
            "language": language,
            "code": code,
        }
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> int:
        """Remove all cached entries. Returns number of files deleted."""
        count = 0
        for path in self.cache_dir.rglob("*.json"):
            path.unlink()
            count += 1
        return count
