"""Skill Registry — Unified dependency resolution for CellClaw pipeline skills.

Resolution order (deterministic, transparent):
    1. Environment variable: CELLCLAW_SKILL_<SKILL_NAME>
    2. Registry file: ~/.cellclaw/skills.json
    3. Fallback relative path from this script's parent

Usage:
    from _skill_registry import resolve_skill_path, import_skill_module
    data_io_path = resolve_skill_path("bio-single-cell-data-io")
    adata = import_skill_module("bio-single-cell-data-io", "samplesheet").load_from_samplesheet(path)
"""

import json
import os
import sys
from pathlib import Path


def _get_env_var(skill_name: str) -> str:
    """Convert skill name to env var key, e.g. bio-single-cell-data-io → CELLCLAW_SKILL_BIO_SINGLE_CELL_DATA_IO."""
    return f"CELLCLAW_SKILL_{skill_name.upper().replace('-', '_')}"


def _get_registry_file() -> Path:
    """Path to the central skills registry JSON."""
    env_registry = os.environ.get("CELLCLAW_SKILLS_REGISTRY")
    if env_registry:
        return Path(env_registry)
    return Path.home() / ".cellclaw" / "skills.json"


def _get_fallback_path(skill_name: str, subpath: str) -> Path:
    """Compute fallback relative path from this script's parent."""
    script_dir = Path(__file__).parent.resolve()
    return script_dir / f"../../../{skill_name}/{subpath}"


def _read_registry(skill_name: str, subpath: str) -> Path | None:
    """Try to resolve skill path from the central registry file."""
    registry_file = _get_registry_file()
    if not registry_file.exists():
        return None
    try:
        with open(registry_file, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    entry = registry.get(skill_name)
    if not entry:
        return None

    # Entry can be a string (path) or a dict with 'path' key
    if isinstance(entry, dict):
        path_str = entry.get("path")
    else:
        path_str = str(entry)

    if not path_str:
        return None

    resolved = Path(path_str).expanduser().resolve() / subpath
    if resolved.exists():
        return resolved
    return None


def resolve_skill_path(skill_name: str, subpath: str = "scripts/python") -> Path:
    """Resolve skill path via env var → registry file → relative fallback.

    Parameters
    ----------
    skill_name : str
        Skill name, e.g. "bio-single-cell-data-io"
    subpath : str
        Subdirectory to append (e.g. "scripts/python", "scripts/r")

    Returns
    -------
    Path
        Absolute path to the skill's scripts directory.

    Raises
    ------
    FileNotFoundError
        If none of the three resolution methods succeed.
    """
    attempted = []

    # 1. Environment variable
    env_key = _get_env_var(skill_name)
    env_path = os.environ.get(env_key)
    if env_path:
        resolved = Path(env_path).expanduser().resolve() / subpath
        if resolved.exists():
            return resolved
        attempted.append(f"Env var {env_key}={env_path} (not found)")
    else:
        attempted.append(f"Env var {env_key} (not set)")

    # 2. Registry file
    registry_path = _read_registry(skill_name, subpath)
    if registry_path is not None:
        return registry_path
    attempted.append(f"Registry file {_get_registry_file()} (missing or no entry)")

    # 3. Fallback relative path
    fallback = _get_fallback_path(skill_name, subpath)
    if fallback.exists():
        return fallback.resolve()
    attempted.append(f"Fallback {fallback} (not found)")

    raise FileNotFoundError(
        f"Cannot resolve skill '{skill_name}' (subpath='{subpath}'). Tried:\n"
        + "\n".join(f"  {i + 1}. {a}" for i, a in enumerate(attempted))
        + "\n\nFix one of:\n"
        f"  • export {env_key}=/path/to/{skill_name}\n"
        f"  • Add to ~/.cellclaw/skills.json: {{\"{skill_name}\": \"/path/to/{skill_name}\"}}\n"
        f"  • Ensure {skill_name} is checked out at ../../../{skill_name}/"
    )


def import_skill_module(skill_name: str, module_name: str, subpath: str = "scripts/python"):
    """Dynamically import a module from a skill's scripts directory.

    Parameters
    ----------
    skill_name : str
        Skill name
    module_name : str
        Python module name (e.g. "samplesheet")
    subpath : str
        Subdirectory within the skill

    Returns
    -------
    module
        Imported module object

    Raises
    ------
    ImportError
        If the module cannot be imported
    """
    skill_path = resolve_skill_path(skill_name, subpath=subpath)
    path_str = str(skill_path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    try:
        return __import__(module_name)
    except ImportError as e:
        raise ImportError(
            f"Failed to import '{module_name}' from skill '{skill_name}' at {skill_path}: {e}"
        ) from e
