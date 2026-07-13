"""Git-based workspace snapshots for reproducible execution.

A hidden git repository lives under ``<workspace>/.metadata/git`` and tracks the
workspace root as its worktree. Snapshots are created automatically at task
boundaries so that the exact file state before/after every job and skill can be
inspected, diffed, or restored.

Operations are best-effort: if git is unavailable or misconfigured, warnings are
logged and the methods return empty/false results without raising.
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GitWorkspaceSnapshot:
    """Best-effort wrapper around a hidden git repo inside a workspace."""

    GIT_DIR_NAME = "git"
    GITIGNORE = ".gitignore"

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)
        self.git_dir = self.workspace_dir / ".metadata" / self.GIT_DIR_NAME
        self._git_available: Optional[bool] = None

    def _git_executable(self) -> Optional[str]:
        """Return the git executable path or None if git is unavailable."""
        if self._git_available is None:
            executable = shutil.which("git")
            self._git_available = executable is not None
            if not self._git_available:
                logger.warning("Git executable not found; workspace snapshots disabled")
        return shutil.which("git") if self._git_available else None

    def _run(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = False,
        timeout: float = 30.0,
        use_git_env: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a git command with the hidden git directory."""
        executable = self._git_executable()
        if executable is None:
            return subprocess.CompletedProcess(
                args=["git", *args],
                returncode=-1,
                stdout="",
                stderr="git not available",
            )

        env = dict(subprocess.os.environ)
        if use_git_env:
            env["GIT_DIR"] = str(self.git_dir)
            env["GIT_WORK_TREE"] = str(self.workspace_dir)
        full_args = [executable, *args]
        try:
            return subprocess.run(
                full_args,
                cwd=str(cwd or self.workspace_dir),
                env=env,
                capture_output=True,
                text=True,
                check=check,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Git command timed out: %s", " ".join(full_args))
            return subprocess.CompletedProcess(
                args=full_args,
                returncode=-1,
                stdout="",
                stderr="timeout",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Git command failed: %s", exc)
            return subprocess.CompletedProcess(
                args=full_args,
                returncode=-1,
                stdout="",
                stderr=str(exc),
            )

    def init(self) -> bool:
        """Initialize the hidden git repository if it does not exist.

        Returns:
            True if a usable git repository exists after the call, False otherwise.
        """
        if self.git_dir.exists():
            # Verify the directory is actually a git repo.
            result = self._run(["rev-parse", "--git-dir"])
            return result.returncode == 0

        executable = self._git_executable()
        if executable is None:
            return False

        self.git_dir.parent.mkdir(parents=True, exist_ok=True)
        result = self._run(
            ["init", "--bare", "--initial-branch=main", str(self.git_dir)],
            use_git_env=False,
        )
        if result.returncode != 0:
            logger.warning("Failed to initialize git repo: %s", result.stderr)
            return False

        # Set a default identity and disable line-ending conversion so commits
        # are reproducible across platforms.
        self._run(["config", "user.email", "homomics@localhost"])
        self._run(["config", "user.name", "HomomicsLab"])
        self._run(["config", "core.autocrlf", "false"])
        return True

    def _ensure_gitignore(self) -> None:
        """Maintain a root gitignore that excludes the metadata git dir."""
        gitignore_path = self.workspace_dir / self.GITIGNORE
        required_line = f"/{self.git_dir.relative_to(self.workspace_dir)}"
        required_line = required_line.replace("\\", "/")
        lines = []
        if gitignore_path.exists():
            lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        if required_line not in lines:
            lines.append(required_line)
            gitignore_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def commit(self, label: str, task_id: str) -> Optional[str]:
        """Stage all workspace files and create a snapshot commit.

        Args:
            label: Human-readable description of the snapshot.
            task_id: Identifier for the run/skill that triggered the snapshot.

        Returns:
            The commit hash, or None if the commit could not be created.
        """
        if not self.init():
            return None

        self._ensure_gitignore()

        message = f"{task_id}: {label}"
        add_result = self._run(["add", "-A"])
        if add_result.returncode != 0:
            logger.warning("Failed to stage files: %s", add_result.stderr)
            return None

        commit_result = self._run(["commit", "-m", message])
        if commit_result.returncode != 0:
            # A commit may fail because there is nothing to commit. This is fine.
            if "nothing to commit" in commit_result.stdout.lower():
                # Return HEAD hash so callers still have a reference.
                head_result = self._run(["rev-parse", "HEAD"])
                if head_result.returncode == 0:
                    return head_result.stdout.strip() or None
            logger.warning("Failed to commit snapshot: %s", commit_result.stderr)
            return None

        head_result = self._run(["rev-parse", "HEAD"])
        if head_result.returncode == 0:
            return head_result.stdout.strip() or None
        return None

    def list_commits(self) -> List[Dict]:
        """Return a list of commits with hash, message, and author_date."""
        if not self.init():
            return []

        fmt = "{%n  \"hash\": \"%H\",%n  \"message\": \"%s\",%n  \"author_date\": \"%aI\"%n}"
        result = self._run(
            ["log", f"--pretty=format:{fmt}", "--no-merges"]
        )
        if result.returncode != 0:
            return []

        raw = result.stdout.strip()
        if not raw:
            return []

        commits = []
        # ``git log --pretty=format`` does not emit separators; each entry is a
        # self-contained JSON object. Wrap the concatenated output into an array
        # by inserting commas and brackets.
        try:
            # Entries are separated by zero or more whitespace; normalize to a
            # single comma so the result is a valid JSON array.
            normalized = ",".join(entry.strip() for entry in raw.split("}") if entry.strip())
            wrapped = "[" + normalized + "]"
            commits = json.loads(wrapped)
        except json.JSONDecodeError:
            # Fallback: parse one entry at a time.
            for entry in raw.split("}"):
                entry = entry.strip()
                if not entry:
                    continue
                if not entry.startswith("{"):
                    entry = "{" + entry
                entry = entry + "}"
                try:
                    commits.append(json.loads(entry))
                except json.JSONDecodeError:
                    continue

        return commits

    def diff(self, commit_a: str, commit_b: str) -> str:
        """Return the ``git diff --stat`` output between two commits."""
        if not self.init():
            return ""

        result = self._run(["diff", commit_a, commit_b, "--stat"])
        if result.returncode != 0:
            logger.warning(
                "Failed to diff commits %s..%s: %s", commit_a, commit_b, result.stderr
            )
            return ""
        return result.stdout.strip()

    def restore(self, commit_id: str) -> bool:
        """Restore the workspace file tree to a given commit.

        The ``.metadata/`` directory is preserved because it is tracked by the
        hidden git dir configuration, not the workspace root.
        """
        if not self.init():
            return False

        result = self._run(["checkout", "-f", commit_id])
        if result.returncode != 0:
            logger.warning(
                "Failed to restore snapshot %s: %s", commit_id, result.stderr
            )
            return False
        return True
