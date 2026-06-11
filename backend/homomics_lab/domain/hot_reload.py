"""Hot-reloading for domains and skills.

Watches domain.yaml files and skill directories for changes,
automatically reloading without service restart.
"""

import asyncio
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.models import DomainDefinition
from homomics_lab.domain.registry import DomainRegistry
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry


class FileWatcher:
    """Simple file modification time watcher.

    Production alternative: use watchdog library (pip install watchdog).
    """

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
            self._update_mtime(path)
        self._callbacks[path].append(callback)

    def unwatch(self, path: Path) -> None:
        """Stop watching a path."""
        path = Path(path).resolve()
        self._callbacks.pop(path, None)
        self._watched_files.pop(path, None)

    def _update_mtime(self, path: Path) -> None:
        """Get the latest modification time of a path (file or directory)."""
        if path.is_file():
            self._watched_files[path] = path.stat().st_mtime
        elif path.is_dir():
            # Track the newest mtime in the directory
            max_mtime = 0.0
            for item in path.rglob("*"):
                if item.is_file():
                    max_mtime = max(max_mtime, item.stat().st_mtime)
            self._watched_files[path] = max_mtime

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
            self._update_mtime(path)
            new_mtime = self._watched_files[path]

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
                    return

            # New domain
            domain = self.loader.load(path)
            self.registry.register(domain, self.loader, path)
            print(f"[HotReload] New domain '{domain.domain}' loaded")

        except Exception as e:
            print(f"[HotReload] Failed to reload {path}: {e}")

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
    ):
        self.registry = skill_registry
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

            loader = SkillLoader(registry=self.registry)
            skill = loader.load_skill(skill_dir)
            self.registry.register(skill)
            print(f"[HotReload] Skill '{skill_id}' reloaded successfully")
        except Exception as e:
            print(f"[HotReload] Failed to reload skill '{skill_id}': {e}")

    async def start(self) -> None:
        await self.watcher.start()

    async def stop(self) -> None:
        await self.watcher.stop()
