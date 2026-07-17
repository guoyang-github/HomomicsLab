"""Core reproducibility skill: capture execution provenance.

Reference implementation for the agent. It mirrors what the platform's
ReproducibilityEngine (homomics_lab/reproducibility/engine.py, driven by
homomics_lab/jobs/runner.py) does for every background job:

- snapshot the runtime environment (homomics_lab/provenance/env_snapshot.py),
- checksum output artifacts (homomics_lab/provenance/recorder.py ``file_record``),
- summarize the reproducibility bundle manifests the job runner has already
  finalized in the workspace (``.metadata/reproducibility_bundle*.json``).

The authoritative bundle for the *current* job is only finalized by the runner
after the job ends, so this script stays read-only: it captures provenance for
the steps it is given and reports the bundles that already exist. When the
``homomics_lab`` package is importable the real helpers are used; otherwise
stdlib equivalents with identical logic keep the script self-contained so it
also runs inside a minimal sandbox.
"""

import hashlib
import json
import mimetypes
import sys
from pathlib import Path


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file (mirrors recorder.sha256_file)."""
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _file_record(path: Path) -> dict:
    """Checksum/size record for one artifact (mirrors recorder.file_record)."""
    record = {"path": str(path), "checksum": None, "size_bytes": 0, "mime_type": ""}
    try:
        if path.is_file():
            record["checksum"] = _sha256_file(path)
            record["size_bytes"] = path.stat().st_size
            mime, _ = mimetypes.guess_type(str(path))
            record["mime_type"] = mime or ""
    except OSError:
        pass
    return record


def _env_snapshot() -> dict:
    """Snapshot the runtime environment via the real provenance helper.

    Falls back to an identical stdlib implementation when ``homomics_lab`` is
    not importable (e.g. inside a sandbox that only has this script).
    """
    try:
        from homomics_lab.provenance.env_snapshot import env_hash, env_snapshot

        snapshot = env_snapshot()
        snapshot["env_hash"] = env_hash(snapshot)
        return snapshot
    except Exception:
        import platform

        packages = []
        try:
            from importlib.metadata import distributions

            packages = sorted(
                {
                    f"{dist.metadata.get('Name')}=={dist.version}"
                    for dist in distributions()
                    if dist.metadata.get("Name") and dist.version
                },
                key=str.lower,
            )
        except Exception:
            pass
        snapshot = {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": packages,
        }
        canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
        snapshot["env_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return snapshot


def _bundle_summary(path: Path) -> dict:
    """Extract a compact summary from a reproducibility bundle manifest."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"path": str(path), "error": "unreadable bundle manifest"}
    snapshot = data.get("execution_snapshot") or {}
    return {
        "path": str(path),
        "project_id": data.get("project_id"),
        "created_at": data.get("created_at"),
        "random_seed": data.get("random_seed"),
        "env_snapshot_hash": data.get("env_snapshot_hash"),
        "skills": sorted((data.get("skill_versions") or {}).get("locked_skills", {})),
        "phases": list((snapshot.get("task_tree") or {}).keys()),
        "code_snippets": len(data.get("agent_code_archive") or []),
        "hitl_decisions": len(data.get("hitl_decisions") or []),
    }


def _find_bundles(workspace_dir: Path) -> list:
    """Summarize reproducibility bundle manifests finalized by the job runner."""
    metadata_dir = workspace_dir / ".metadata"
    if not metadata_dir.is_dir():
        return []
    return [
        _bundle_summary(p)
        for p in sorted(metadata_dir.glob("reproducibility_bundle*.json"))
    ]


def main(skill_inputs: dict) -> dict:
    """Build a provenance record from the execution log."""
    execution_log = skill_inputs["execution_log"]
    artifacts = skill_inputs.get("artifacts", [])
    workspace_dir = Path(skill_inputs.get("workspace_dir") or ".")

    steps = execution_log.get("steps", [])
    provenance = {
        "workflow_id": execution_log.get("workflow_id", "unknown"),
        "steps": [
            {
                "skill_id": step.get("skill_id"),
                "inputs": step.get("inputs"),
                "runtime": step.get("runtime"),
            }
            for step in steps
        ],
        "artifacts": [
            _file_record(Path(a.get("path") if isinstance(a, dict) else a))
            for a in artifacts
        ],
        "environment": _env_snapshot(),
        "reproducibility_bundles": _find_bundles(workspace_dir),
        "recorded_at": execution_log.get("recorded_at"),
    }

    return {"provenance": provenance}


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
