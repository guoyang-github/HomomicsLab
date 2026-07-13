"""Artifact classification and collection for inline UI rendering.

A skill result may reference files (CSV, figures, HTML reports, H5AD, ...).
This module turns those file references into small, normalized ``artifact``
envelopes (``{kind, mime, name, path, size}``) the frontend renderer registry
keys on to pick an inline renderer (image / table / html / pdf / json / file).

The mapping is intentionally extension-driven and best-effort: unknown files
fall back to ``kind="file"`` so the UI can still offer a download.
"""

import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

# Extension -> canonical renderer kind. Checked before the MIME guess so that
# domain-specific formats (e.g. .h5ad) route correctly even without a MIME type.
_EXTENSION_KIND: Dict[str, str] = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".svg": "image",
    ".webp": "image",
    ".csv": "table",
    ".tsv": "table",
    ".html": "html",
    ".htm": "html",
    ".pdf": "pdf",
    ".json": "json",
    ".h5ad": "anndata",
    ".h5": "anndata",
}

_MIME_KIND: Dict[str, str] = {
    "image": "image",
    "text/csv": "table",
    "text/tab-separated-values": "table",
    "text/html": "html",
    "application/pdf": "pdf",
    "application/json": "json",
}


def classify(path: Path) -> (str, str):
    """Return ``(kind, mime)`` for a file path (extension-first, then MIME)."""
    name = path.name if isinstance(path, Path) else str(path)
    ext = Path(name).suffix.lower()
    mime, _ = mimetypes.guess_type(name)
    mime = mime or "application/octet-stream"

    if ext in _EXTENSION_KIND:
        return _EXTENSION_KIND[ext], mime
    if mime in _MIME_KIND:
        return _MIME_KIND[mime], mime
    major = mime.split("/", 1)[0]
    if major == "image":
        return "image", mime
    return "file", mime


def build_artifact(path: Path) -> Optional[Dict[str, Any]]:
    """Build a normalized artifact envelope for an existing file, else None."""
    try:
        p = Path(path)
        if not p.is_file():
            return None
        kind, mime = classify(p)
        stat = p.stat()
        return {
            "kind": kind,
            "mime": mime,
            "name": p.name,
            "path": str(p),
            "size": stat.st_size,
        }
    except OSError:
        return None


def collect_result_artifacts(workspace: Any, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect artifact envelopes for file outputs referenced in ``result``.

    Only files inside the workspace are considered (matches the existing
    artifact-registry scoping). The result is never mutated here.
    """
    if workspace is None or not isinstance(result, dict):
        return []
    workspace_dir = getattr(workspace, "workspace_dir", None)
    artifacts: List[Dict[str, Any]] = []
    seen = set()
    for value in result.values():
        if not isinstance(value, (str, Path)):
            continue
        path = Path(value)
        if not path.is_file():
            continue
        if workspace_dir is not None:
            try:
                path.relative_to(workspace_dir)
            except ValueError:
                continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        artifact = build_artifact(path)
        if artifact is not None:
            artifacts.append(artifact)
    return artifacts
