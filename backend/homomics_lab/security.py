"""Security primitives for HomomicsLab.

This module provides path sandboxing, identifier validation, and safe-execution
helpers used by tools, skills, and API endpoints. It is designed to be
opt-in-friendly for local development while enforceable in production.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from homomics_lab.config import settings


class PathSecurityError(ValueError):
    """Raised when a path escapes the allowed workspace."""


class IdentifierSecurityError(ValueError):
    """Raised when a user-controlled identifier contains unsafe characters."""


# Allow letters, digits, underscore, hyphen, and dot, but not leading dots or
# path separators. This keeps IDs filesystem-safe and URL-safe.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")
_MAX_ID_LEN = 128


def validate_project_id(project_id: str) -> str:
    """Validate and normalize a project identifier.

    Raises:
        IdentifierSecurityError: if the identifier is unsafe.
    """
    if not isinstance(project_id, str) or not project_id:
        raise IdentifierSecurityError("project_id must be a non-empty string")
    if len(project_id) > _MAX_ID_LEN:
        raise IdentifierSecurityError(f"project_id exceeds {_MAX_ID_LEN} characters")
    if not _SAFE_ID_RE.match(project_id):
        raise IdentifierSecurityError(
            "project_id contains unsafe characters; allowed: A-Z, a-z, 0-9, _, -, ."
        )
    # Reject path-like segments that slip through the regex.
    if ".." in project_id or "/" in project_id or "\\" in project_id:
        raise IdentifierSecurityError("project_id must not contain path separators")
    return project_id


def validate_session_id(session_id: str) -> str:
    """Validate a session identifier.

    Session IDs are allowed to be UUIDs or URL-safe tokens, so the rules are
    slightly looser than project IDs while still forbidding path traversal.
    """
    if not isinstance(session_id, str) or not session_id:
        raise IdentifierSecurityError("session_id must be a non-empty string")
    if len(session_id) > _MAX_ID_LEN:
        raise IdentifierSecurityError(f"session_id exceeds {_MAX_ID_LEN} characters")
    if ".." in session_id or "/" in session_id or "\\" in session_id:
        raise IdentifierSecurityError("session_id must not contain path separators")
    if not re.match(r"^[A-Za-z0-9_\-:.@]+$", session_id):
        raise IdentifierSecurityError(
            "session_id contains unsafe characters; allowed: A-Z, a-z, 0-9, _, -, :, ., @"
        )
    return session_id


def get_workspace_root() -> Path:
    """Return the root directory inside which all user files must live."""
    return Path(settings.data_dir).resolve()


def safe_path(
    path: Union[str, Path],
    root: Optional[Union[str, Path]] = None,
    must_exist: bool = False,
    allow_absolute_within_root: bool = True,
) -> Path:
    """Resolve a user-supplied path and ensure it stays within ``root``.

    Args:
        path: The user-supplied path (absolute or relative).
        root: Allowed root directory. Defaults to ``settings.data_dir``.
        must_exist: If True, raise FileNotFoundError when the path does not exist.
        allow_absolute_within_root: If False, reject absolute paths outright.

    Raises:
        PathSecurityError: if the path escapes the root or is invalid.
        FileNotFoundError: if ``must_exist`` is True and the path is missing.
    """
    if path is None or str(path) == "":
        raise PathSecurityError("path must not be empty")

    raw_path = Path(path)
    if raw_path.is_absolute() and not allow_absolute_within_root:
        raise PathSecurityError("absolute paths are not allowed")

    root_path = Path(root).resolve() if root else get_workspace_root()
    resolved = (root_path / raw_path).resolve()

    # Verify resolved path is within root. Use a loop to handle symlinks.
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise PathSecurityError(
            f"Path '{path}' escapes allowed workspace root '{root_path}'"
        ) from exc

    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    return resolved


def safe_open_path(
    path: Union[str, Path],
    root: Optional[Union[str, Path]] = None,
    must_exist: bool = True,
) -> Path:
    """Convenience wrapper for read-only operations."""
    return safe_path(path, root=root, must_exist=must_exist)


def safe_write_path(
    path: Union[str, Path],
    root: Optional[Union[str, Path]] = None,
    create_parents: bool = True,
) -> Path:
    """Convenience wrapper for write operations; creates parent dirs."""
    resolved = safe_path(path, root=root, must_exist=False)
    if create_parents:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def sanitize_filename(filename: str) -> str:
    """Sanitize an uploaded filename to a safe basename.

    Strips path components and collapses dangerous characters.
    """
    if not isinstance(filename, str):
        raise ValueError("filename must be a string")
    # Drop any directory components.
    base = Path(filename).name
    if not base or base in {"." , ".."}:
        raise ValueError("invalid filename")
    # Replace any remaining non-alphanumeric-ish characters with underscore,
    # but keep a few safe separators.
    safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", base)
    if not safe or safe.startswith("."):
        raise ValueError("invalid filename after sanitization")
    return safe


def is_sandbox_forced() -> bool:
    """Return whether the configuration forces sandboxed execution."""
    # In production we default to forcing sandboxing unless explicitly disabled.
    return getattr(settings, "force_sandbox", True)


def validate_git_url(url: str) -> None:
    """Raise PathSecurityError if the git URL is not in the configured whitelist.

    When ``settings.allowed_skill_git_urls`` is empty, all URLs are allowed and a
    warning is logged. Otherwise the URL must start with one of the configured
    prefixes.
    """
    import logging

    logger = logging.getLogger(__name__)

    allowed = getattr(settings, "allowed_skill_git_urls", [])
    if not allowed:
        logger.warning(
            "No allowed_skill_git_urls configured; accepting git URL %s. "
            "Set HOMOMICS_ALLOWED_SKILL_GIT_URLS in production.",
            url,
        )
        return

    for prefix in allowed:
        if url.startswith(prefix):
            return

    raise PathSecurityError(
        f"Git URL '{url}' is not in the configured whitelist. "
        f"Allowed prefixes: {', '.join(allowed)}"
    )


def safe_extractall(zip_file, extract_dir: Union[str, Path]) -> None:
    """Extract a zip archive while preventing path traversal attacks.

    Rejects entries that contain ``..`` components, absolute paths, or would
    resolve outside ``extract_dir``. Raises ``PathSecurityError`` on violation.
    """
    from zipfile import ZipFile

    if not isinstance(zip_file, ZipFile):
        raise TypeError("zip_file must be a zipfile.ZipFile instance")

    target_root = Path(extract_dir).resolve()
    for member in zip_file.infolist():
        member_path = Path(member.filename)
        # Reject absolute paths and parent references.
        if member_path.is_absolute():
            raise PathSecurityError(f"Zip entry has absolute path: {member.filename}")
        if ".." in member_path.parts:
            raise PathSecurityError(f"Zip entry escapes archive: {member.filename}")

        target_path = (target_root / member_path).resolve()
        try:
            target_path.relative_to(target_root)
        except ValueError as exc:
            raise PathSecurityError(
                f"Zip entry escapes extraction directory: {member.filename}"
            ) from exc

        if member.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as src, open(target_path, "wb") as dst:
                dst.write(src.read())
