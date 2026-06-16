"""VersionLocker — project-level version locking for reproducibility.

Locks:
  - Skill versions (by skill ID → version hash)
  - Python environment (pip freeze / conda export)
  - HomomicsLab version

Provides verification against the locked state to detect drift.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import homomics_lab


@dataclass
class VersionLock:
    """A locked snapshot of all versions for a project."""

    project_id: str
    locked_at: str
    skills: Dict[str, str]  # skill_id → version
    skill_checksums: Dict[str, str]  # skill_id → scripts_dir hash
    environment: str  # pip freeze output
    python_version: str
    homomics_version: str


@dataclass
class LockVerificationResult:
    """Result of verifying current state against a lock."""

    compatible: bool
    version_mismatches: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    environment_diff: Optional[str] = None


def _compute_scripts_checksum(scripts_dir: Path) -> str:
    """Compute a combined checksum of all scripts in a directory."""
    import hashlib

    h = hashlib.sha256()
    if scripts_dir.exists():
        for f in sorted(scripts_dir.rglob("*")):
            if f.is_file():
                h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _capture_pip_freeze() -> str:
    """Capture current environment packages.

    Uses ``importlib.metadata`` so the lock works even in venvs without
    ``pip`` installed (e.g. uv-managed environments).
    """
    try:
        from importlib.metadata import distributions

        lines = [f"{d.metadata['Name']}=={d.version}" for d in distributions()]
        return "\n".join(sorted(lines))
    except Exception:
        return ""


class VersionLocker:
    """Manages version locking for projects."""

    LOCK_FILENAME = "version.lock"

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir

    def lock_project(
        self,
        project_id: str,
        skill_registry,
    ) -> VersionLock:
        """Create a version lock for the current project state."""
        skills = {}
        checksums = {}

        for skill in skill_registry.list_all():
            skills[skill.id] = skill.version
            scripts_dir = skill.metadata.get("scripts_dir")
            if scripts_dir:
                checksums[skill.id] = _compute_scripts_checksum(Path(scripts_dir))

        lock = VersionLock(
            project_id=project_id,
            locked_at=datetime.now(timezone.utc).isoformat(),
            skills=skills,
            skill_checksums=checksums,
            environment=_capture_pip_freeze(),
            python_version=f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
            homomics_version=getattr(homomics_lab, "__version__", "unknown"),
        )

        self._save_lock(lock)
        return lock

    def verify(self, skill_registry) -> LockVerificationResult:
        """Verify current state against the stored lock."""
        lock = self._load_lock()
        if lock is None:
            return LockVerificationResult(
                compatible=True,
                warnings=["No lock file found"],
            )

        mismatches = []
        missing = []

        for skill_id, locked_version in lock.skills.items():
            current = skill_registry.get(skill_id)
            if current is None:
                missing.append(skill_id)
            elif current.version != locked_version:
                mismatches.append(
                    f"{skill_id}: locked={locked_version}, current={current.version}"
                )

        # Check for new skills not in lock
        current_skills = {s.id for s in skill_registry.list_all()}
        for skill_id in current_skills - set(lock.skills.keys()):
            mismatches.append(f"{skill_id}: not in lock (new skill)")

        compatible = len(mismatches) == 0 and len(missing) == 0

        return LockVerificationResult(
            compatible=compatible,
            version_mismatches=mismatches,
            missing_skills=missing,
        )

    def _save_lock(self, lock: VersionLock) -> None:
        """Save lock to workspace metadata."""
        lock_path = self.workspace_dir / ".metadata" / self.LOCK_FILENAME
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(
                {
                    "project_id": lock.project_id,
                    "locked_at": lock.locked_at,
                    "skills": lock.skills,
                    "skill_checksums": lock.skill_checksums,
                    "environment": lock.environment,
                    "python_version": lock.python_version,
                    "homomics_version": lock.homomics_version,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _load_lock(self) -> Optional[VersionLock]:
        """Load lock from workspace metadata."""
        lock_path = self.workspace_dir / ".metadata" / self.LOCK_FILENAME
        if not lock_path.exists():
            return None

        data = json.loads(lock_path.read_text(encoding="utf-8"))
        return VersionLock(
            project_id=data["project_id"],
            locked_at=data["locked_at"],
            skills=data["skills"],
            skill_checksums=data.get("skill_checksums", {}),
            environment=data["environment"],
            python_version=data["python_version"],
            homomics_version=data["homomics_version"],
        )
