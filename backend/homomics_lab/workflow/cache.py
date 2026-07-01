"""Content-addressable workflow cache for incremental execution.

The cache stores task results keyed by a deterministic hash of:
  - skill id + version
  - task parameters
  - hashes of upstream inputs / file inputs

Hits are returned as restored results and the corresponding TaskNode is marked
COMPLETED without re-execution. This works for both the local Orchestrator path
and as a complement to Nextflow's own resume mechanism.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.tasks.models import TaskNode


DEFAULT_CONTENT_HASH_LIMIT = 10 * 1024 * 1024  # 10 MB


@dataclass
class CacheEntry:
    """A single cached task result."""

    key: str
    result: Dict[str, Any]
    artifacts: List[Path] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.result.get("status") != "error" and self.result.get("error") is None


class WorkflowCache:
    """Filesystem-backed content-addressable cache for workflow tasks."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = (
            cache_dir
            or getattr(settings, "workflow_cache_dir", None)
            or (Path(settings.data_dir) / ".cache" / "workflow")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._content_hash_limit = getattr(
            settings, "workflow_cache_content_hash_limit", DEFAULT_CONTENT_HASH_LIMIT
        )

    @staticmethod
    def compute_hash(data: Any) -> str:
        """Return a stable sha256 hex digest for arbitrary JSON-serializable data."""
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def compute_task_key(
        self,
        task: TaskNode,
        skill: Optional[SkillDefinition] = None,
        upstream_results: Optional[Dict[str, Any]] = None,
        workspace_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Compute a deterministic cache key for a task.

        The key includes skill identity/version, task parameters, and hashes of
        all inputs that could affect the output.
        """
        skill_id = skill.id if skill else task.name
        skill_version = "unknown"
        if skill is not None:
            skill_version = skill.version
        elif task.skills_required:
            skill_version = "latest"

        # Parameter component.
        params = dict(task.parameters)
        params.pop("_timeout_seconds", None)
        params.pop("_trace_id", None)

        # Upstream result component: hash of dependency task results.
        upstream_hashes: Dict[str, str] = {}
        if upstream_results:
            for dep_id, dep_result in sorted(upstream_results.items()):
                upstream_hashes[dep_id] = self.compute_hash(dep_result)

        # File input component: hash workspace input files when referenced.
        file_hashes: Dict[str, str] = {}
        inputs_to_hash = workspace_inputs
        if inputs_to_hash is None:
            inputs_to_hash = {}
            for key, value in sorted(task.parameters.items()):
                if isinstance(value, (str, Path)):
                    inputs_to_hash[key] = Path(value)
                elif isinstance(value, dict) and "path" in value:
                    inputs_to_hash[key] = Path(value["path"])
        if inputs_to_hash:
            for key, value in sorted(inputs_to_hash.items()):
                if isinstance(value, (str, Path)):
                    path = Path(value)
                    if path.is_file():
                        file_hashes[key] = self._hash_file(path)
                    else:
                        file_hashes[key] = str(value)
                else:
                    file_hashes[key] = self.compute_hash(value)

        key_data = {
            "skill_id": skill_id,
            "skill_version": skill_version,
            "parameters": params,
            "upstream": upstream_hashes,
            "inputs": file_hashes,
        }
        return self.compute_hash(key_data)

    def _hash_file(self, path: Path) -> str:
        """Hash file contents up to a limit; beyond that use size+mtime."""
        stat = path.stat()
        if stat.st_size > self._content_hash_limit:
            return hashlib.sha256(
                f"{path.name}:{stat.st_size}:{stat.st_mtime}".encode("utf-8")
            ).hexdigest()

        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _entry_dir(self, key: str) -> Path:
        """Spread keys across subdirectories to avoid huge flat directories."""
        return self.cache_dir / key[:2] / key[2:4] / key

    def get(self, key: str) -> Optional[CacheEntry]:
        """Retrieve a cached entry by key."""
        entry_dir = self._entry_dir(key)
        metadata_path = entry_dir / "metadata.json"
        result_path = entry_dir / "result.json"
        if not metadata_path.exists() or not result_path.exists():
            return None

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        artifacts_dir = entry_dir / "artifacts"
        artifacts: List[Path] = []
        if artifacts_dir.exists():
            artifacts = sorted(p for p in artifacts_dir.rglob("*") if p.is_file())

        return CacheEntry(key=key, result=result, artifacts=artifacts, metadata=metadata)

    def put(
        self,
        key: str,
        result: Dict[str, Any],
        artifacts: Optional[List[Path]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a task result in the cache."""
        entry_dir = self._entry_dir(key)
        entry_dir.mkdir(parents=True, exist_ok=True)

        metadata = metadata or {}
        metadata["cache_key"] = key
        metadata["artifact_count"] = len(artifacts or [])

        (entry_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, default=str), encoding="utf-8"
        )
        (entry_dir / "result.json").write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )

        artifacts_dir = entry_dir / "artifacts"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        for src in artifacts or []:
            src_path = Path(src)
            if not src_path.exists():
                continue
            dst = artifacts_dir / src_path.name
            if src_path.is_dir():
                shutil.copytree(src_path, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dst)

    def invalidate(self, key: str) -> bool:
        """Remove a cached entry."""
        entry_dir = self._entry_dir(key)
        if not entry_dir.exists():
            return False
        shutil.rmtree(entry_dir)
        return True

    def clear(self) -> int:
        """Clear the entire cache. Returns number of entries removed."""
        count = 0
        for result_path in list(self.cache_dir.rglob("result.json")):
            entry_dir = result_path.parent
            if entry_dir.is_dir():
                count += 1
                shutil.rmtree(entry_dir)

        for prefix_dir in list(self.cache_dir.iterdir()):
            if not prefix_dir.is_dir():
                continue
            for mid_dir in list(prefix_dir.iterdir()):
                if mid_dir.is_dir() and not any(mid_dir.iterdir()):
                    mid_dir.rmdir()
            if not any(prefix_dir.iterdir()):
                prefix_dir.rmdir()
        return count
