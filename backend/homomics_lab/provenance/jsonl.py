"""Append-only JSONL provenance and run logs for project workspaces.

Writes human-readable, one-record-per-line trails under a workspace
``.metadata/`` directory:

* ``provenance.jsonl`` — one line per produced artifact linking the output
  file to its run (job), code hash, and environment hash.
* ``runs.jsonl`` — one line per execution (job) summary.

These complement the SQLite ``ProvenanceRecorder`` (structured queries) with a
diff-friendly, append-only audit trail that travels with the workspace and is
trivial to inspect with ``cat``/``jq``.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOCKS: Dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    key = str(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append one JSON record as a single line. Best-effort (never raises)."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=False)
        with _lock_for(path):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to append jsonl %s: %s", path, exc)


def _metadata_dir(workspace_dir: Path) -> Path:
    return Path(workspace_dir) / ".metadata"


def record_run(workspace_dir: Path, record: Dict[str, Any]) -> None:
    """Append a single execution summary line to ``runs.jsonl``."""
    append_jsonl(_metadata_dir(workspace_dir) / "runs.jsonl", record)


def record_provenance(
    workspace_dir: Path,
    *,
    job_id: str,
    skill_id: str,
    skill_version: str,
    code_hash: str,
    env_hash: str,
    output_files: List[Any],
    status: str,
    started_at: Optional[str],
    ended_at: Optional[str],
) -> None:
    """Append one provenance line per output artifact.

    If a run produced no files, a single line with ``output=null`` is still
    written so the run -> code -> environment linkage is never lost.
    """
    base = {
        "job_id": job_id,
        "skill_id": skill_id,
        "skill_version": skill_version,
        "code_hash": code_hash,
        "env_hash": env_hash,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
    }
    path = _metadata_dir(workspace_dir) / "provenance.jsonl"
    if output_files:
        for file_record in output_files:
            entry = dict(base)
            entry["output"] = (
                file_record.to_dict()
                if hasattr(file_record, "to_dict")
                else {"path": str(file_record)}
            )
            append_jsonl(path, entry)
    else:
        entry = dict(base)
        entry["output"] = None
        append_jsonl(path, entry)
