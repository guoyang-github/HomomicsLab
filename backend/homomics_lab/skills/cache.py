"""Result cache for deterministic skill executions."""

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any, Dict, Optional


class SkillCache:
    """Disk-based cache for skill results keyed by skill id + stable inputs."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, skill_id: str, inputs: Dict[str, Any], fingerprint: str = "") -> Optional[Any]:
        """Return cached result if present."""
        key = self._compute_key(skill_id, inputs, fingerprint)
        path = self.cache_dir / f"{key}.pkl"
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def put(self, skill_id: str, inputs: Dict[str, Any], result: Any, fingerprint: str = "") -> None:
        """Store a result in the cache."""
        key = self._compute_key(skill_id, inputs, fingerprint)
        path = self.cache_dir / f"{key}.pkl"
        with open(path, "wb") as f:
            pickle.dump(result, f)

    def invalidate(self, skill_id: str, inputs: Dict[str, Any], fingerprint: str = "") -> bool:
        """Remove a cached entry. Returns True if an entry was removed."""
        key = self._compute_key(skill_id, inputs, fingerprint)
        path = self.cache_dir / f"{key}.pkl"
        if path.exists():
            path.unlink()
            return True
        return False

    def clear(self) -> int:
        """Remove all cached entries. Returns number removed."""
        removed = 0
        for path in self.cache_dir.glob("*.pkl"):
            path.unlink()
            removed += 1
        return removed

    @staticmethod
    def _compute_key(skill_id: str, inputs: Dict[str, Any], fingerprint: str) -> str:
        """Compute a stable cache key."""
        payload = json.dumps(
            {"skill_id": skill_id, "inputs": inputs, "fingerprint": fingerprint},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
