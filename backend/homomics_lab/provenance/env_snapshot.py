"""Content-addressed environment snapshots for reproducibility.

Captures the Python runtime and installed distributions once, hashes the
canonical form, and stores it under ``<metadata_dir>/env/<hash>.json``. The
same environment is written only once; later runs reuse the existing file and
reference it by hash.
"""

import hashlib
import json
import logging
import platform
import sys
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def collect_distributions() -> List[str]:
    """Return sorted ``name==version`` lines for installed distributions.

    Uses ``importlib.metadata`` so it works in virtualenvs without ``pip`` and
    never spawns a subprocess.
    """
    try:
        from importlib.metadata import distributions
    except Exception:  # pragma: no cover
        return []
    lines: List[str] = []
    for dist in distributions():
        name = dist.metadata.get("Name")
        version = dist.version
        if name and version:
            lines.append(f"{name}=={version}")
    return sorted(set(lines), key=str.lower)


def env_snapshot() -> Dict[str, object]:
    """Build a serializable snapshot of the current runtime environment."""
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": collect_distributions(),
    }


def env_hash(snapshot: Dict[str, object]) -> str:
    """Stable SHA-256 of the canonical snapshot representation."""
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def store_env_snapshot(metadata_dir: Path) -> str:
    """Write ``env/<hash>.json`` once and return the environment hash.

    Best-effort: returns an empty string if the snapshot cannot be captured or
    persisted, so reproducibility bookkeeping never blocks execution.
    """
    try:
        snapshot = env_snapshot()
        digest = env_hash(snapshot)
        env_dir = Path(metadata_dir) / "env"
        env_dir.mkdir(parents=True, exist_ok=True)
        target = env_dir / f"{digest}.json"
        if not target.exists():
            target.write_text(
                json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False),
                encoding="utf-8",
            )
        return digest
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to store environment snapshot: %s", exc)
        return ""
