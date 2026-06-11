"""Builtin tools for HomomicsLab.

These are atomic capabilities that agents use to interact with system resources.
They are registered into ToolRegistry at startup.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


def file_read(path: str, encoding: str = "utf-8", limit_bytes: Optional[int] = None) -> str:
    """Read contents of a file.

    Args:
        path: Absolute or workspace-relative file path.
        encoding: Text encoding. Use "binary" for raw bytes (returned as base64).
        limit_bytes: Maximum bytes to read (safety limit).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

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
    """Write content to a file.

    Args:
        path: Target file path.
        content: Content to write.
        encoding: Text encoding.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=encoding)
    return {"path": str(file_path), "bytes_written": len(content.encode(encoding))}


def file_list(directory: str, pattern: Optional[str] = None) -> List[str]:
    """List files in a directory.

    Args:
        directory: Directory path.
        pattern: Optional glob pattern (e.g., "*.h5ad").
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if pattern:
        return [str(p) for p in dir_path.glob(pattern)]
    return [str(p) for p in dir_path.iterdir() if p.is_file()]


def shell_exec(command: str, cwd: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    """Execute a shell command.

    WARNING: This tool executes arbitrary shell commands.
    Use with caution and only in trusted environments.

    Args:
        command: Shell command to execute.
        cwd: Working directory for the command.
        timeout: Timeout in seconds.
    """
    import subprocess

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


async def web_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Search the web using DuckDuckGo.

    Args:
        query: Search query.
        num_results: Maximum number of results.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        # Fallback: return a mock result if duckduckgo-search not installed
        return [
            {
                "title": "DuckDuckGo search not available",
                "href": "",
                "body": "Install duckduckgo-search package to use this tool.",
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
        description="Read the contents of a file",
        handler=file_read,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "encoding": {"type": "string", "default": "utf-8"},
                "limit_bytes": {"type": "integer", "description": "Max bytes to read"},
            },
            "required": ["path"],
        },
    )

    registry.register_builtin(
        name="file_write",
        description="Write content to a file",
        handler=file_write,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path", "content"],
        },
    )

    registry.register_builtin(
        name="file_list",
        description="List files in a directory",
        handler=file_list,
        input_schema={
            "type": "object",
            "properties": {
                "directory": {"type": "string"},
                "pattern": {"type": "string", "description": "Glob pattern, e.g., '*.h5ad'"},
            },
            "required": ["directory"],
        },
    )

    registry.register_builtin(
        name="shell_exec",
        description="Execute a shell command (use with caution)",
        handler=shell_exec,
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
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
