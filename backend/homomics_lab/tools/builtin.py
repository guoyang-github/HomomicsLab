"""Builtin tools for HomomicsLab.

These are atomic capabilities that agents use to interact with system resources.
They are registered into ToolRegistry at startup.

Security notes:
- All file operations are restricted to the configured workspace root.
- ``shell_exec`` runs inside the configured skill sandbox (bubblewrap/container)
  when available; in local mode it is gated by ``force_sandbox`` and
  ``interactive_mode`` settings.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.security import safe_open_path, safe_write_path
from homomics_lab.skills.sandbox import Sandbox


def _workspace_root() -> Path:
    """Return the configured workspace root (lazy so tests can monkeypatch it)."""
    return Path(settings.data_dir).resolve()


def _resolve_workspace_path(path: str, must_exist: bool = False) -> Path:
    """Resolve a user-supplied path against the workspace root."""
    return safe_open_path(path, root=_workspace_root(), must_exist=must_exist)


def file_read(path: str, encoding: str = "utf-8", limit_bytes: Optional[int] = None) -> str:
    """Read contents of a file.

    Args:
        path: Workspace-relative file path.
        encoding: Text encoding. Use "binary" for raw bytes (returned as base64).
        limit_bytes: Maximum bytes to read (safety limit).
    """
    file_path = _resolve_workspace_path(path, must_exist=True)

    if encoding == "binary":
        data = file_path.read_bytes()
        if limit_bytes and len(data) > limit_bytes:
            data = data[:limit_bytes]
        import base64
        return base64.b64encode(data).decode("ascii")

    text = file_path.read_text(encoding=encoding)
    if limit_bytes and len(text.encode(encoding)) > limit_bytes:
        text = text[:limit_bytes]
    return text


def file_write(path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Write content to a file within the workspace.

    Args:
        path: Workspace-relative target file path.
        content: Content to write.
        encoding: Text encoding.
    """
    file_path = safe_write_path(path, root=_workspace_root())
    file_path.write_text(content, encoding=encoding)
    return {"path": str(file_path), "bytes_written": len(content.encode(encoding))}


def file_list(directory: str, pattern: Optional[str] = None) -> List[str]:
    """List files in a workspace directory.

    Args:
        directory: Workspace-relative directory path.
        pattern: Optional glob pattern (e.g., "*.h5ad").
    """
    dir_path = _resolve_workspace_path(directory, must_exist=True)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    if pattern:
        return [str(p) for p in dir_path.glob(pattern) if p.is_file()]
    return [str(p) for p in dir_path.iterdir() if p.is_file()]


def file_edit(path: str, old_string: str, new_string: str) -> Dict[str, Any]:
    """Edit a file by replacing an exact substring.

    Args:
        path: Workspace-relative file path.
        old_string: Exact text to replace.
        new_string: Replacement text.
    """
    file_path = _resolve_workspace_path(path, must_exist=True)
    content = file_path.read_text(encoding="utf-8")
    if old_string not in content:
        raise ValueError("old_string not found in file")

    content = content.replace(old_string, new_string, 1)
    file_path.write_text(content, encoding="utf-8")
    return {"path": str(file_path), "replaced": True}


def shell_exec(command: str, cwd: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    """Execute a shell command inside the configured sandbox.

    WARNING: This tool is high-risk. In production ``force_sandbox`` is enabled
    by default, which requires an isolated sandbox (bubblewrap or container).
    The legacy unsandboxed local path is only available when ``force_sandbox``
    is explicitly disabled.

    Args:
        command: Shell command to execute.
        cwd: Working directory for the command (workspace-relative).
        timeout: Timeout in seconds.
    """
    import asyncio

    if not command or not isinstance(command, str):
        raise ValueError("command must be a non-empty string")

    # Validate cwd stays inside workspace.
    workdir: Path = _workspace_root()
    if cwd:
        workdir = _resolve_workspace_path(cwd, must_exist=False)

    backend = settings.skill_sandbox_backend

    # Production / force_sandbox mode: require real isolation for shell commands.
    if settings.force_sandbox:
        if backend == "local":
            raise RuntimeError(
                "shell_exec refused: force_sandbox is enabled but backend is 'local'. "
                "Use 'bubblewrap' or 'container' for shell execution."
            )
        if backend == "auto" and not _isolated_sandbox_available():
            raise RuntimeError(
                "shell_exec refused: force_sandbox is enabled and no isolated "
                "sandbox (bubblewrap/container) is available."
            )
        sandbox = Sandbox.create(backend, workdir, container_image=settings.skill_container_image)
        output = asyncio.run(sandbox.run_command(command, cwd=workdir, timeout_seconds=timeout))
        return {
            "returncode": 0,
            "stdout": output,
            "stderr": "",
            "sandbox_backend": backend if backend != "auto" else _detected_sandbox_name(sandbox),
        }

    # Legacy unsandboxed local-dev path.
    if not settings.interactive_mode:
        import subprocess
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(workdir),
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "sandbox_backend": "local_unsandboxed_legacy",
        }

    raise RuntimeError(
        "shell_exec is disabled: enable an isolated sandbox or explicitly disable "
        "force_sandbox for local development."
    )


def _detected_sandbox_name(sandbox) -> str:
    """Return a human-readable name for an auto-selected sandbox."""
    from homomics_lab.skills.sandbox import BubblewrapSandbox, ContainerSandbox
    if isinstance(sandbox, BubblewrapSandbox):
        return "bubblewrap"
    if isinstance(sandbox, ContainerSandbox):
        return "container"
    return "local"


def _isolated_sandbox_available() -> bool:
    """Return True if bubblewrap or a container engine is available."""
    from homomics_lab.skills.sandbox import BubblewrapSandbox, ContainerSandbox
    return BubblewrapSandbox.is_available() or ContainerSandbox.is_available()


async def web_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Search the web using DuckDuckGo.

    Args:
        query: Search query.
        num_results: Maximum number of results.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        # Fallback: return a mock result if ddgs package is not installed
        return [
            {
                "title": "Web search not available",
                "href": "",
                "body": "Install ddgs package to use this tool.",
            }
        ]

    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=num_results)
        return [
            {
                "title": r.get("title", ""),
                "href": r.get("href", ""),
                "body": r.get("body", ""),
            }
            for r in results
        ]


def memory_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search the semantic memory store.

    This is a placeholder that delegates to the SemanticMemory instance.
    The actual implementation will be bound at runtime.
    """
    return []


def register_all_builtin_tools(registry) -> None:
    """Register all builtin tools into a ToolRegistry."""
    registry.register_builtin(
        name="file_read",
        description="Read the contents of a file within the workspace",
        handler=file_read,
        risk_level="medium",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative file path"},
                "encoding": {"type": "string", "default": "utf-8"},
                "limit_bytes": {"type": "integer", "description": "Max bytes to read"},
            },
            "required": ["path"],
        },
    )

    registry.register_builtin(
        name="file_write",
        description="Write content to a file within the workspace",
        handler=file_write,
        risk_level="high",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative file path"},
                "content": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path", "content"],
        },
    )

    registry.register_builtin(
        name="file_list",
        description="List files in a workspace directory",
        handler=file_list,
        risk_level="medium",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Workspace-relative directory"},
                "pattern": {"type": "string", "description": "Glob pattern, e.g., '*.h5ad'"},
            },
            "required": ["directory"],
        },
    )

    registry.register_builtin(
        name="file_edit",
        description="Edit a file by replacing an exact substring within the workspace",
        handler=file_edit,
        risk_level="high",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative file path"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    )

    registry.register_builtin(
        name="shell_exec",
        description="Execute a shell command inside the configured sandbox",
        handler=shell_exec,
        risk_level="high",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "description": "Workspace-relative working directory"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["command"],
        },
        metadata={"dangerous": True},
    )

    registry.register_builtin(
        name="web_search",
        description="Search the web using DuckDuckGo",
        handler=web_search,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    )

    registry.register_builtin(
        name="memory_search",
        description="Search the semantic memory store",
        handler=memory_search,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    )
