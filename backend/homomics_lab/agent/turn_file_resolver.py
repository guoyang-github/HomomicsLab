"""FileReferenceResolver — resolves uploaded file mentions in user messages.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from homomics_lab.config import settings

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnRunner
    from homomics_lab.tasks.task_tree import TaskTree


class FileReferenceResolver:
    """Resolve bare filenames in user messages and attach them to task trees."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    def resolve_uploaded_file_references(
        self,
        user_message: Optional[str],
        project_id: str,
    ) -> List[Tuple[str, str]]:
        """Find bare filenames in the message that exist as uploaded project files.

        Returns a list of ``(filename, resolved_path)`` tuples. Both the project
        raw directory and the workspace data directory are checked so files
        uploaded via the file API are discoverable without explicit ``@file:``
        references.
        """
        if not user_message:
            return []

        candidates = re.findall(r"[\w\-\.]+\.\w{2,8}", user_message)
        seen: set[str] = set()
        resolved: List[Tuple[str, str]] = []

        for candidate in candidates:
            filename = Path(candidate).name
            if filename in seen or not filename:
                continue
            seen.add(filename)

            for base in (
                settings.data_dir / "raw" / project_id,
                settings.data_dir / "workspaces" / project_id / "data",
            ):
                candidate_path = base / filename
                if candidate_path.is_file():
                    resolved.append((filename, str(candidate_path.resolve())))
                    break

        return resolved

    def attach_uploaded_files_to_tree(
        self,
        tree: "TaskTree",
        user_message: Optional[str],
        project_id: str,
    ) -> None:
        """Inject request context and uploaded file paths into task parameters.

        This lets skills/agents know the concrete user objective and which files
        it refers to, even when the message only mentions a filename without an
        ``@file:`` reference. For single-step skills the file is usually the
        primary input; for workflows it is added as a fallback when a task does
        not already specify an input file.
        """
        files = self.resolve_uploaded_file_references(user_message, project_id)
        primary_path = files[0][1] if files else None
        for task in tree.tasks:
            if task.parameters is None:
                task.parameters = {}
            if user_message and "user_request" not in task.parameters:
                task.parameters["user_request"] = user_message
            if primary_path and "input_file" not in task.parameters:
                task.parameters["input_file"] = primary_path
            # Also expose the full list for multi-file tasks.
            if files and "uploaded_files" not in task.parameters:
                task.parameters["uploaded_files"] = [
                    {"filename": name, "path": path} for name, path in files
                ]
