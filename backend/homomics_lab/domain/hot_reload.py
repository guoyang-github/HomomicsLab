"""Hot-reloading for domains and skills.

Watches domain.yaml files and skill directories for changes,
automatically reloading without service restart.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.registry import DomainRegistry
from homomics_lab.skills.registry import SkillRegistry


class FileWatcher:
    """Simple file modification time watcher.

    Production alternative: use watchdog library (pip install watchdog).
    """

    # Directories that are expensive or irrelevant to scan for skill/domain reloads.
    IGNORED_DIRS: frozenset[str] = frozenset({
        ".git", "node_modules", ".venv", "venv", "__pycache__",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".benchmarks",
        "data", "bak", "dist", "build", ".gitignore", ".metadata",
    })
    # Large/binary file extensions that should not trigger reloads.
    IGNORED_EXTENSIONS: frozenset[str] = frozenset({
        ".h5ad", ".h5", ".hdf5", ".bam", ".cram", ".sam",
        ".fastq", ".fq", ".fasta", ".fa", ".gz", ".zip", ".tar",
        ".parquet", ".zarr", ".db", ".sqlite", ".pkl", ".pickle",
    })
    # Skip individual files larger than this to avoid blocking on data artifacts.
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    def __init__(self, check_interval: float = 2.0):
        self.check_interval = check_interval
        self._watched_files: Dict[Path, float] = {}
        self._callbacks: Dict[Path, List[Callable]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def watch(self, path: Path, callback: Callable) -> None:
        """Watch a file or directory for changes."""
        path = Path(path).resolve()
        if path not in self._callbacks:
            self._callbacks[path] = []
            # Use -1.0 as a sentinel: the first check will capture the current
            # mtime without firing callbacks, preventing a startup flood of
            # "changed" events for every watched skill/domain.
            self._watched_files[path] = -1.0
        self._callbacks[path].append(callback)

    def unwatch(self, path: Path) -> None:
        """Stop watching a path."""
        path = Path(path).resolve()
        self._callbacks.pop(path, None)
        self._watched_files.pop(path, None)

    def _should_skip_path(self, item: Path) -> bool:
        """Return True if a path should be ignored during scanning."""
        # Skip hidden files/dirs and known non-source directories.
        for part in item.parts:
            if part.startswith(".") and part != ".":
                return True
            if part in self.IGNORED_DIRS:
                return True
        if item.suffix.lower() in self.IGNORED_EXTENSIONS:
            return True
        return False

    def _update_mtime_sync(self, path: Path) -> float:
        """Get the latest modification time of a path (file or directory).

        This is the blocking implementation; it must be called from a worker thread.
        """
        if path.is_file():
            try:
                if path.stat().st_size > self.MAX_FILE_SIZE_BYTES:
                    return 0.0
                return path.stat().st_mtime
            except OSError:
                return 0.0
        elif path.is_dir():
            max_mtime = 0.0
            try:
                for item in path.rglob("*"):
                    if self._should_skip_path(item):
                        continue
                    if item.is_file():
                        try:
                            if item.stat().st_size > self.MAX_FILE_SIZE_BYTES:
                                continue
                            max_mtime = max(max_mtime, item.stat().st_mtime)
                        except OSError:
                            continue
            except OSError:
                pass
            return max_mtime
        return 0.0

    async def _update_mtime(self, path: Path) -> None:
        """Async wrapper that offloads blocking filesystem calls to a thread."""
        self._watched_files[path] = await asyncio.to_thread(
            self._update_mtime_sync, path
        )

    async def start(self) -> None:
        """Start watching in a background task."""
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _watch_loop(self) -> None:
        """Main watch loop."""
        while self._running:
            await self._check_once()
            await asyncio.sleep(self.check_interval)

    async def _check_once(self) -> None:
        """Check all watched paths for changes."""
        for path, callbacks in list(self._callbacks.items()):
            old_mtime = self._watched_files.get(path, 0.0)
            await self._update_mtime(path)
            new_mtime = self._watched_files.get(path, 0.0)

            # Sentinel value: first check seeds the baseline without firing
            # callbacks so we don't treat every existing file as "changed".
            if old_mtime < 0:
                continue

            if new_mtime > old_mtime:
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(path)
                        else:
                            callback(path)
                    except Exception as e:
                        print(f"Hot-reload callback error for {path}: {e}")


class DomainHotReloader:
    """Hot-reload domains when their domain.yaml changes."""

    def __init__(
        self,
        domain_registry: DomainRegistry,
        domain_loader: DomainLoader,
        watcher: Optional[FileWatcher] = None,
    ):
        self.registry = domain_registry
        self.loader = domain_loader
        self.watcher = watcher or FileWatcher()

    def watch_domain(self, domain_yaml_path: Path) -> None:
        """Start watching a domain.yaml file."""
        self.watcher.watch(domain_yaml_path, self._on_domain_change)

    async def _on_domain_change(self, path: Path) -> None:
        """Handle domain.yaml change."""
        print(f"[HotReload] Domain file changed: {path}")
        try:
            # Find which domain this is
            for domain_id, source_path in list(self.registry._source_paths.items()):
                if source_path == path:
                    # Unregister old
                    self.registry.unregister(domain_id)
                    # Reload
                    domain = self.loader.load(path)
                    self.registry.register(domain, self.loader, path)
                    print(f"[HotReload] Domain '{domain_id}' reloaded successfully")
                    self._refresh_intent_analyzers()
                    return

            # New domain
            domain = self.loader.load(path)
            self.registry.register(domain, self.loader, path)
            print(f"[HotReload] New domain '{domain.domain}' loaded")
            self._refresh_intent_analyzers()

        except Exception as e:
            print(f"[HotReload] Failed to reload {path}: {e}")

    @staticmethod
    def _refresh_intent_analyzers() -> None:
        """Notify live intent analyzers that domain definitions changed."""
        try:
            from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer

            CascadeIntentAnalyzer.reload_all()
            print("[HotReload] Intent analyzers refreshed")
        except Exception as e:
            print(f"[HotReload] Failed to refresh intent analyzers: {e}")

    async def start(self) -> None:
        await self.watcher.start()

    async def stop(self) -> None:
        await self.watcher.stop()


class SkillHotReloader:
    """Hot-reload skills when their SKILL.md or scripts change."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        watcher: Optional[FileWatcher] = None,
        skill_store: Optional[Any] = None,
        capability_index: Optional[Any] = None,
    ):
        self.registry = skill_registry
        self.skill_store = skill_store
        self.capability_index = capability_index
        self.watcher = watcher or FileWatcher()
        self._skill_dirs: Dict[Path, str] = {}  # dir_path -> skill_id

    def watch_skill_dir(self, skill_dir: Path, skill_id: Optional[str] = None) -> None:
        """Watch a skill directory for changes."""
        skill_dir = Path(skill_dir).resolve()
        if skill_id is None:
            skill_id = skill_dir.name
        self._skill_dirs[skill_dir] = skill_id
        self.watcher.watch(skill_dir, self._on_skill_change)

    def watch_skills_directory(self, skills_dir: Path) -> None:
        """Watch all skills in a directory."""
        skills_dir = Path(skills_dir).resolve()
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                self.watch_skill_dir(skill_dir)

    async def _on_skill_change(self, path: Path) -> None:
        """Handle skill directory change."""
        # Find which skill this is
        skill_dir = path if path.is_dir() else path.parent
        while skill_dir not in self._skill_dirs and skill_dir.parent != skill_dir:
            skill_dir = skill_dir.parent

        if skill_dir not in self._skill_dirs:
            return

        skill_id = self._skill_dirs[skill_dir]
        print(f"[HotReload] Skill '{skill_id}' changed at {skill_dir}")

        try:
            from homomics_lab.skills.loader import SkillLoader
            from homomics_lab.skills.skill_store import SkillStore

            loader = SkillLoader(registry=self.registry)
            skill = loader.load_skill(skill_dir)
            self.registry.register(skill)

            # Keep SkillStore metadata in sync (name/version/category/sha256).
            if self.skill_store is not None:
                for key, entry in list(self.skill_store._meta.items()):
                    if entry.get("id") != skill.id:
                        continue
                    entry["name"] = skill.name
                    entry["version"] = skill.version
                    entry["category"] = skill.category
                    source_dir = Path(entry.get("source_dir", skill_dir))
                    if source_dir.is_dir():
                        entry["sha256"] = SkillStore._compute_sha256(source_dir)
                    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.skill_store._save_meta()

            # Re-index in the capability index so retrieval stays consistent.
            if self.capability_index is not None:
                asyncio.create_task(self.capability_index.index_skill(skill))

            print(f"[HotReload] Skill '{skill_id}' reloaded successfully")
        except Exception as e:
            print(f"[HotReload] Failed to reload skill '{skill_id}': {e}")

    async def start(self) -> None:
        await self.watcher.start()

    async def stop(self) -> None:
        await self.watcher.stop()
