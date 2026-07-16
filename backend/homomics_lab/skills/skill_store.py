"""SkillStore — unified skill lifecycle management.

SkillStore sits on top of SkillRegistry and manages:
  - import / update / remove from local dirs, git repos, or uploaded archives
  - namespace tracking
  - enable / disable flags
  - validation reports
  - test execution
  - version locking per project

The runtime registry only sees enabled skills. Disabled skills remain in the
store metadata and can be re-enabled without re-importing.
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from homomics_lab.security import safe_extractall, validate_git_url
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


@dataclass
class ValidationReport:
    """Result of validating a skill directory."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TestReport:
    """Result of running a skill's tests."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    tests_run: int = 0
    tests_passed: int = 0


@dataclass
class VersionLock:
    """Project-level skill version lock."""

    project_id: str
    locked_at: str
    skills: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "locked_at": self.locked_at,
            "skills": self.skills,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionLock":
        return cls(
            project_id=data["project_id"],
            locked_at=data["locked_at"],
            skills=data.get("skills", {}),
        )


class SkillStoreError(Exception):
    """Raised when SkillStore operations fail."""

    pass


class SkillStore:
    """Unified skill lifecycle store backed by a JSON metadata file.

    Args:
        registry: Runtime skill registry. If None, a private registry is used.
        store_dir: Directory for persisted metadata.
        skills_dir: Canonical runtime directory for skill sources. Imported skills
            are copied here; drop-in skills are registered in place. Defaults to
            ``./skills``.
    """

    DEFAULT_NAMESPACE = "default"

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        store_dir: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
    ):
        self.registry = registry or SkillRegistry()
        self.store_dir = (
            (store_dir or Path("./data/skill_store")).expanduser().resolve()
        )
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = (skills_dir or Path("./skills")).expanduser().resolve()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.store_dir / "skills.json"
        self._meta: Dict[str, Dict[str, Any]] = {}
        self._load_meta()

    # ─────────────────────────────────────────
    # Metadata persistence
    # ─────────────────────────────────────────

    def _load_meta(self) -> None:
        if self.meta_path.exists():
            text = self.meta_path.read_text(encoding="utf-8").strip()
            if not text:
                self._meta = {}
                return
            try:
                self._meta = json.loads(text)
            except json.JSONDecodeError as exc:
                raise SkillStoreError(f"Corrupt skill store metadata: {exc}") from exc
        else:
            self._meta = {}

    def _save_meta(self) -> None:
        self.meta_path.write_text(
            json.dumps(self._meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _meta_key(self, skill_id: str, namespace: str) -> str:
        return f"{namespace}:{skill_id}"

    def _record_meta(
        self,
        skill: SkillDefinition,
        namespace: str,
        source: str,
        source_dir: Path,
        enabled: bool = True,
        trusted: bool = False,
        sha256: Optional[str] = None,
    ) -> None:
        key = self._meta_key(skill.id, namespace)
        self._meta[key] = {
            "id": skill.id,
            "namespace": namespace,
            "name": skill.name,
            "version": skill.version,
            "category": skill.category,
            "source": source,
            "source_dir": str(source_dir),
            "enabled": enabled,
            "trusted": trusted,
            "sha256": sha256,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_meta()

    @staticmethod
    def _compute_sha256(skill_dir: Path) -> str:
        """Compute a sha256 digest of all files under a skill directory."""
        h = hashlib.sha256()
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                h.update(path.relative_to(skill_dir).as_posix().encode("utf-8"))
                h.update(b"\0")
                h.update(path.read_bytes())
                h.update(b"\0")
        return h.hexdigest()

    @staticmethod
    def _is_trusted_source(source: str) -> bool:
        return source == "builtin"

    # ─────────────────────────────────────────
    # Import / update / remove
    # ─────────────────────────────────────────

    def import_skill(
        self,
        source: str,
        namespace: Optional[str] = None,
        skill_id: Optional[str] = None,
        enable: bool = True,
    ) -> SkillDefinition:
        """Import a skill from a local path, git URL, or uploaded archive.

        Args:
            source: Path, git URL, or zip archive path.
            namespace: Logical namespace. Defaults to "default".
            skill_id: Optional override for the canonical skill id.
            enable: Whether to enable the skill immediately.

        Returns:
            Loaded SkillDefinition.
        """
        namespace = namespace or self.DEFAULT_NAMESPACE
        source_path = self._resolve_source(source)

        if not source_path.exists():
            raise SkillStoreError(f"Skill source not found: {source}")

        validation = self.validate_skill(source_path)
        if not validation.valid:
            raise SkillStoreError(
                "Skill validation failed:\n"
                + "\n".join(f"  - {e}" for e in validation.errors)
            )

        # Copy skill into the canonical skills directory unless it is already
        # there (e.g. a user drop-in skill). This keeps the runtime source of
        # truth under ``skills_dir`` while allowing imports from git/zip/external.
        loader = SkillLoader(registry=self.registry)
        preview = loader.load_discovery(source_path)
        imported_skill_id = skill_id or preview.id

        target_dir = self.skills_dir / imported_skill_id
        source_is_canonical = source_path.resolve() == target_dir.resolve()
        if not source_is_canonical:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_path, target_dir)

        # Load at discovery level; the runtime will activate on first execution.
        skill = loader.load_discovery(target_dir)
        if skill_id:
            skill.id = skill_id

        # Compute content digest and determine default trust.
        sha256 = self._compute_sha256(target_dir)
        trusted = self._is_trusted_source(source)

        # Normalize source to a stable category so runtime trust checks apply.
        # The original origin is preserved in metadata["origin"].
        skill.metadata["source"] = source if trusted else "imported"
        skill.metadata["origin"] = source
        skill.metadata["source_dir"] = str(target_dir)
        skill.metadata["namespace"] = namespace
        skill.metadata["trusted"] = trusted
        skill.metadata["sha256"] = sha256
        skill.metadata["disclosure_level"] = "discovery"

        if enable:
            self.registry.register(skill)
        self._record_meta(
            skill,
            namespace,
            source,
            target_dir,
            enabled=enable,
            trusted=trusted,
            sha256=sha256,
        )
        return skill

    def register_dropin(
        self,
        source_dir: Path,
        namespace: str = "user",
        enable: bool = True,
    ) -> SkillDefinition:
        """Register a skill that already lives under ``skills_dir`` in place.

        This is used for the user drop-in directory: the skill is not copied,
        but its metadata is persisted and it is registered with the runtime.
        """
        source_dir = Path(source_dir).expanduser().resolve()
        if not source_dir.exists():
            raise SkillStoreError(f"Skill source not found: {source_dir}")

        validation = self.validate_skill(source_dir)
        if not validation.valid:
            raise SkillStoreError(
                "Skill validation failed:\n"
                + "\n".join(f"  - {e}" for e in validation.errors)
            )

        loader = SkillLoader(registry=self.registry)
        skill = loader.load_discovery(source_dir)
        sha256 = self._compute_sha256(source_dir)

        skill.metadata["source"] = "dropin"
        skill.metadata["origin"] = str(source_dir)
        skill.metadata["source_dir"] = str(source_dir)
        skill.metadata["namespace"] = namespace
        skill.metadata["trusted"] = False
        skill.metadata["sha256"] = sha256
        skill.metadata["disclosure_level"] = "discovery"

        if enable:
            self.registry.register(skill)
        self._record_meta(
            skill,
            namespace,
            "dropin",
            source_dir,
            enabled=enable,
            trusted=False,
            sha256=sha256,
        )
        return skill

    def update_skill(
        self,
        skill_id: str,
        source: str,
        namespace: Optional[str] = None,
    ) -> SkillDefinition:
        """Re-import a skill from a new source."""
        namespace = namespace or self.DEFAULT_NAMESPACE
        key = self._meta_key(skill_id, namespace)
        if key not in self._meta:
            raise SkillStoreError(
                f"Skill '{skill_id}' not found in namespace '{namespace}'"
            )

        enabled = self._meta[key].get("enabled", True)
        # Remove old runtime registration and search index entry
        self.registry.remove(skill_id)

        skill = self.import_skill(
            source=source,
            namespace=namespace,
            skill_id=skill_id,
            enable=enabled,
        )
        return skill

    def _is_managed_skill_dir(self, path: Path) -> bool:
        """Return True if ``path`` is a directory managed under ``skills_dir``."""
        try:
            path.resolve().relative_to(self.skills_dir.resolve())
        except ValueError:
            return False
        return path.is_dir()

    def remove_skill(self, skill_id: str, namespace: Optional[str] = None) -> None:
        """Remove a skill from the store and runtime registry.

        If the skill's source directory lives under the canonical ``skills_dir``,
        the directory is also deleted. Builtin and out-of-tree sources are only
        unregistered.
        """
        namespace = namespace or self.DEFAULT_NAMESPACE
        key = self._meta_key(skill_id, namespace)
        if key not in self._meta:
            raise SkillStoreError(
                f"Skill '{skill_id}' not found in namespace '{namespace}'"
            )

        entry = self._meta.pop(key)
        target_dir = Path(entry.get("source_dir", ""))
        if self._is_managed_skill_dir(target_dir):
            shutil.rmtree(target_dir)
        self.registry.remove(skill_id)
        self._save_meta()

    # ─────────────────────────────────────────
    # Enable / disable
    # ─────────────────────────────────────────

    def enable_skill(
        self, skill_id: str, namespace: Optional[str] = None
    ) -> SkillDefinition:
        """Enable a previously disabled skill."""
        namespace = namespace or self.DEFAULT_NAMESPACE
        key = self._meta_key(skill_id, namespace)
        if key not in self._meta:
            raise SkillStoreError(
                f"Skill '{skill_id}' not found in namespace '{namespace}'"
            )

        entry = self._meta[key]
        if entry.get("enabled", True):
            skill = self.registry.get(skill_id)
            if skill is not None:
                return skill

        target_dir = Path(entry["source_dir"])
        loader = SkillLoader(registry=self.registry)
        skill = loader.load_skill(target_dir)
        skill.id = skill_id
        skill.metadata["source"] = entry["source"]
        skill.metadata["source_dir"] = str(target_dir)
        skill.metadata["namespace"] = namespace
        skill.metadata["trusted"] = entry.get("trusted", False)
        skill.metadata["sha256"] = entry.get("sha256")
        self.registry.register(skill)

        entry["enabled"] = True
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_meta()
        return skill

    def disable_skill(self, skill_id: str, namespace: Optional[str] = None) -> None:
        """Disable a skill without removing it from the store."""
        namespace = namespace or self.DEFAULT_NAMESPACE
        key = self._meta_key(skill_id, namespace)
        if key not in self._meta:
            raise SkillStoreError(
                f"Skill '{skill_id}' not found in namespace '{namespace}'"
            )

        if self.registry.get(skill_id) is not None:
            self.registry._skills.pop(skill_id, None)

        self._meta[key]["enabled"] = False
        self._meta[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_meta()

    def trust_skill(
        self,
        skill_id: str,
        trusted: bool = True,
        namespace: Optional[str] = None,
    ) -> SkillDefinition:
        """Mark a skill as trusted or untrusted.

        Trusted skills are allowed to execute scripts and shell commands.
        Untrusted external/community skills are rejected at execution time.

        If ``namespace`` is omitted, the store searches across all namespaces
        for the first matching skill id.
        """
        if namespace is None:
            key = None
            for k, entry in self._meta.items():
                if entry.get("id") == skill_id:
                    key = k
                    namespace = entry.get("namespace", self.DEFAULT_NAMESPACE)
                    break
            if key is None:
                raise SkillStoreError(f"Skill '{skill_id}' not found in any namespace")
        else:
            key = self._meta_key(skill_id, namespace)

        if key not in self._meta:
            raise SkillStoreError(
                f"Skill '{skill_id}' not found in namespace '{namespace}'"
            )

        entry = self._meta[key]
        entry["trusted"] = trusted
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()

        skill = self.registry.get(skill_id)
        if skill is None:
            skill = self.enable_skill(skill_id, namespace)
        skill.metadata["trusted"] = trusted
        if trusted:
            # Clear any explicit trust_level override so resolution falls back
            # to the trusted flag + source (VERIFIED/COMMUNITY).
            skill.metadata.pop("trust_level", None)
            entry.pop("trust_level", None)

        self._save_meta()
        return skill

    # ─────────────────────────────────────────
    # Query
    # ─────────────────────────────────────────

    def list_skills(
        self,
        namespace: Optional[str] = None,
        enabled_only: bool = False,
        category: Optional[str] = None,
    ) -> List[SkillDefinition]:
        """List skills in the store.

        If namespace is omitted, all namespaces are returned.  Because the
        runtime registry uses canonical skill ids without a namespace prefix,
        only one skill with the same id can be enabled at a time; the returned
        list is de-duplicated by id.
        """
        seen: set = set()
        results: List[SkillDefinition] = []
        for key, entry in self._meta.items():
            if namespace is not None and entry.get("namespace") != namespace:
                continue
            if category is not None and entry.get("category") != category:
                continue
            is_enabled = entry.get("enabled", True)
            if not is_enabled and enabled_only:
                continue
            skill_id = entry["id"]
            if skill_id in seen:
                continue
            skill = self.registry.get(skill_id)
            registry_matches = (
                skill is not None
                and skill.metadata.get("namespace") == entry.get("namespace")
            )
            if (skill is None or not registry_matches) and is_enabled:
                # Runtime registry lost the skill, re-enable from store
                try:
                    skill = self.enable_skill(skill_id, entry.get("namespace"))
                except SkillStoreError:
                    continue
            elif skill is None or not registry_matches:
                # Load a discovery-level view for listing without registering
                try:
                    source_dir = Path(entry["source_dir"])
                    skill = SkillLoader(registry=self.registry).load_discovery(
                        source_dir
                    )
                except Exception:
                    continue
            if skill is not None:
                skill.metadata["enabled"] = is_enabled
                seen.add(skill_id)
                results.append(skill)
        return results

    def get_skill(
        self,
        skill_id: str,
        namespace: Optional[str] = None,
    ) -> Optional[SkillDefinition]:
        """Get a skill by id and optional namespace.

        Disabled skills are only returned when ``namespace`` is explicitly
        provided and the caller is prepared to handle a disabled entry; the
        namespace-free lookup never implicitly re-enable a skill.
        """
        if namespace is None:
            skill = self.registry.get(skill_id)
            if skill is not None:
                return skill
            for entry in self._meta.values():
                if entry["id"] == skill_id and entry.get("enabled", True):
                    return self.enable_skill(skill_id, entry.get("namespace"))
            return None
        key = self._meta_key(skill_id, namespace)
        if key not in self._meta:
            return None
        return self.registry.get(skill_id)

    def get_meta(
        self,
        skill_id: str,
        namespace: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get store metadata for a skill."""
        if namespace is None:
            for entry in self._meta.values():
                if entry["id"] == skill_id:
                    return dict(entry)
            return None
        key = self._meta_key(skill_id, namespace)
        return dict(self._meta[key]) if key in self._meta else None

    # ─────────────────────────────────────────
    # Validation & testing
    # ─────────────────────────────────────────

    @staticmethod
    def validate_skill(skill_dir: Path) -> ValidationReport:
        """Validate a skill directory structure."""
        errors: List[str] = []
        warnings: List[str] = []

        if not skill_dir.exists():
            errors.append(f"Skill directory does not exist: {skill_dir}")
            return ValidationReport(valid=False, errors=errors)

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append("Missing SKILL.md")

        # Scripts are optional for all skill types (OpenClaw-style). Only warn
        # when a scripts/ directory is present but empty.
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            script_files = [p for p in scripts_dir.rglob("*") if p.is_file()]
            if not script_files:
                warnings.append("scripts/ directory is empty")

        requirements = skill_dir / "requirements.txt"
        environment = skill_dir / "environment.yml"
        r_dependencies = skill_dir / "dependencies.R"
        if (
            scripts_dir.exists()
            and not requirements.exists()
            and not environment.exists()
            and not r_dependencies.exists()
        ):
            warnings.append(
                "scripts/ present but no requirements.txt, environment.yml or dependencies.R found"
            )

        valid = len(errors) == 0
        return ValidationReport(valid=valid, errors=errors, warnings=warnings)

    def run_tests(self, skill_id: str, namespace: Optional[str] = None) -> TestReport:
        """Run pytest in the skill's tests/ directory if present."""
        namespace = namespace or self.DEFAULT_NAMESPACE
        meta = self.get_meta(skill_id, namespace)
        if meta is None:
            return TestReport(success=False, stderr=f"Skill '{skill_id}' not found")

        source_dir = Path(meta["source_dir"])
        tests_dir = source_dir / "tests"
        if not tests_dir.exists():
            return TestReport(
                success=True,
                stdout="No tests/ directory found; nothing to run.",
                tests_run=0,
                tests_passed=0,
            )

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", str(tests_dir), "-q"],
                cwd=str(source_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return TestReport(success=False, stderr="Test execution timed out")
        except Exception as exc:
            return TestReport(success=False, stderr=str(exc))

        # Parse rough pass/fail count from pytest summary line
        stdout = result.stdout
        stderr = result.stderr
        tests_run = 0
        tests_passed = 0
        for line in stdout.splitlines():
            if "passed" in line and "failed" in line:
                parts = line.split()
                try:
                    tests_run = int(parts[0])
                    tests_passed = tests_run - int(parts[2])
                except (ValueError, IndexError):
                    pass
                break
            if "passed" in line:
                parts = line.split()
                try:
                    tests_passed = int(parts[0])
                    tests_run = tests_passed
                except (ValueError, IndexError):
                    pass
                break

        return TestReport(
            success=result.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            tests_run=tests_run,
            tests_passed=tests_passed,
        )

    # ─────────────────────────────────────────
    # Version locking
    # ─────────────────────────────────────────

    def lock_versions(self, project_id: str) -> VersionLock:
        """Create a version lock from currently enabled skills."""
        skills: Dict[str, str] = {}
        for skill in self.registry.list_all():
            ns = skill.metadata.get("namespace", self.DEFAULT_NAMESPACE)
            key = self._meta_key(skill.id, ns)
            if key in self._meta and self._meta[key].get("enabled", True):
                skills[f"{ns}/{skill.id}"] = skill.version

        lock = VersionLock(
            project_id=project_id,
            locked_at=datetime.now(timezone.utc).isoformat(),
            skills=skills,
        )
        return lock

    def save_lock_file(self, project_id: str, path: Path) -> VersionLock:
        """Save a version lock to a project-level homomics.lock file."""
        lock = self.lock_versions(project_id)
        path.write_text(
            json.dumps(lock.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return lock

    def load_lock_file(self, path: Path) -> VersionLock:
        """Load a version lock from a project-level homomics.lock file."""
        if not path.exists():
            raise SkillStoreError(f"Lock file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return VersionLock.from_dict(data)

    def verify_lock(self, lock: VersionLock) -> ValidationReport:
        """Verify current enabled skills against a version lock."""
        errors: List[str] = []
        warnings: List[str] = []

        current = self.lock_versions(lock.project_id).skills
        for full_id, locked_version in lock.skills.items():
            if full_id not in current:
                errors.append(f"Locked skill '{full_id}' is not currently enabled")
                continue
            if current[full_id] != locked_version:
                errors.append(
                    f"Version mismatch for '{full_id}': locked {locked_version}, current {current[full_id]}"
                )

        for full_id in current:
            if full_id not in lock.skills:
                warnings.append(f"Skill '{full_id}' is enabled but not in lock file")

        return ValidationReport(
            valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # ─────────────────────────────────────────
    # Source resolution
    # ─────────────────────────────────────────

    def _resolve_source(self, source: str) -> Path:
        """Resolve a source string to a local skill directory.

        Supports:
          - Local directory path
          - Git URL (cloned to temp dir)
          - Zip archive path (extracted to temp dir)
        """
        parsed = urlparse(source)

        # Local directory
        local_path = Path(source).expanduser().resolve()
        if local_path.exists() and local_path.is_dir():
            return local_path

        # Git URL
        if source.endswith(".git") or parsed.scheme in ("http", "https", "ssh"):
            validate_git_url(source)
            temp_dir = Path(tempfile.mkdtemp(prefix="homomics_skill_git_"))
            clone_dir = temp_dir / "skill"
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", source, str(clone_dir)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except subprocess.CalledProcessError as exc:
                raise SkillStoreError(
                    f"Failed to clone git repo: {exc.stderr}"
                ) from exc
            except FileNotFoundError as exc:
                raise SkillStoreError("git command not found") from exc
            # If repo root contains skills/ subdir, caller should point deeper;
            # otherwise treat clone root as the skill directory.
            return clone_dir

        # Zip archive
        if local_path.exists() and local_path.suffix == ".zip":
            temp_dir = Path(tempfile.mkdtemp(prefix="homomics_skill_zip_"))
            with zipfile.ZipFile(local_path, "r") as zf:
                safe_extractall(zf, temp_dir)
            # Heuristic: if zip contains a single top-level directory, use it
            entries = [e for e in temp_dir.iterdir() if e.is_dir()]
            if len(entries) == 1 and (entries[0] / "SKILL.md").exists():
                return entries[0]
            return temp_dir

        raise SkillStoreError(f"Unsupported or unreachable skill source: {source}")
