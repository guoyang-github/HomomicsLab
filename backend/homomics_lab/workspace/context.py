"""Execution-time workspace context.

A context variable lets the orchestration layer route all skill I/O for the
current turn/run into the active project's workspace without threading a
project_id through every agent and skill call.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Optional

from homomics_lab.workspace.manager import WorkspaceManager

current_workspace: ContextVar[Optional[WorkspaceManager]] = ContextVar(
    "current_workspace", default=None
)


def get_current_workspace() -> Optional[WorkspaceManager]:
    """Return the workspace manager for the current execution context."""
    return current_workspace.get()


@contextmanager
def workspace_context(workspace: WorkspaceManager) -> Generator[None, None, None]:
    """Set the active workspace for the duration of the context."""
    token = current_workspace.set(workspace)
    try:
        yield
    finally:
        current_workspace.reset(token)
