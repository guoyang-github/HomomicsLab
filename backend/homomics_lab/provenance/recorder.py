"""Record and query execution provenance."""

import hashlib
import json
import logging
import mimetypes
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.provenance.models import ExecutionProvenance, FileRecord

logger = logging.getLogger(__name__)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_record(path: Path) -> FileRecord:
    """Build a FileRecord with checksum and size."""
    if path.exists():
        checksum = sha256_file(path)
        size = path.stat().st_size
        mime, _ = mimetypes.guess_type(str(path))
        return FileRecord(
            path=str(path),
            checksum=checksum,
            size_bytes=size,
            mime_type=mime or "",
        )
    return FileRecord(path=str(path))


def collect_input_files(inputs: Dict[str, Any]) -> List[FileRecord]:
    """Scan inputs for existing file paths and record checksums."""
    records: List[FileRecord] = []
    seen = set()

    def _scan(value: Any) -> None:
        if isinstance(value, str):
            p = Path(value)
            if p.exists() and p.is_file() and str(p) not in seen:
                seen.add(str(p))
                records.append(file_record(p))
        elif isinstance(value, dict):
            for v in value.values():
                _scan(v)
        elif isinstance(value, list):
            for v in value:
                _scan(v)

    _scan(inputs)
    return records


def collect_output_files(working_dir: Path) -> List[FileRecord]:
    """Record checksums for files produced in the working directory.

    Only the top-level files are scanned to avoid accidentally walking
    large project trees (e.g. ``.venv``, ``node_modules``) when the
    scheduler is given a broad working directory. Nested skill outputs are
    tracked via explicit artifact registration instead.
    """
    records: List[FileRecord] = []
    if not working_dir.exists():
        return records
    for path in working_dir.iterdir():
        if path.is_file() and path.name not in {
            "__skill_script__.py",
            "__skill_script__.R",
            "__skill_result__.json",
        }:
            records.append(file_record(path))
    return records


class ProvenanceRecorder:
    """Persist execution provenance to a local SQLite database."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.data_dir / ".metadata" / "provenance.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provenance (
                    execution_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    skill_version TEXT NOT NULL,
                    project_id TEXT,
                    session_id TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    record_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_provenance_skill ON provenance(skill_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_provenance_project ON provenance(project_id)"
            )

    def record(self, provenance: ExecutionProvenance) -> None:
        """Persist a provenance record."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO provenance (
                        execution_id, skill_id, skill_version, project_id, session_id,
                        started_at, ended_at, record_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        provenance.execution_id,
                        provenance.skill_id,
                        provenance.skill_version,
                        provenance.project_id,
                        provenance.session_id,
                        provenance.started_at.isoformat() if provenance.started_at else None,
                        provenance.ended_at.isoformat() if provenance.ended_at else None,
                        json.dumps(provenance.to_dict(), ensure_ascii=False),
                    ),
                )
        except Exception as exc:
            logger.warning("Failed to persist provenance: %s", exc)

    def list_by_project(
        self,
        project_id: str,
        limit: int = 100,
    ) -> List[ExecutionProvenance]:
        """Load provenance records for a project."""
        records: List[ExecutionProvenance] = []
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT record_json FROM provenance
                    WHERE project_id = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (project_id, limit),
                ).fetchall()
            for row in rows:
                data = json.loads(row[0])
                records.append(self._dict_to_provenance(data))
        except Exception as exc:
            logger.warning("Failed to load provenance: %s", exc)
        return records

    @staticmethod
    def _dict_to_provenance(data: Dict[str, Any]) -> ExecutionProvenance:
        return ExecutionProvenance(
            execution_id=data["execution_id"],
            skill_id=data["skill_id"],
            skill_version=data["skill_version"],
            project_id=data.get("project_id"),
            session_id=data.get("session_id"),
            parameters=data.get("parameters", {}),
            input_files=[FileRecord(**f) for f in data.get("input_files", [])],
            output_files=[FileRecord(**f) for f in data.get("output_files", [])],
            sandbox_backend=data.get("sandbox_backend", ""),
            container_image=data.get("container_image"),
            container_digest=data.get("container_digest"),
            dependency_manifest=data.get("dependency_manifest", {}),
            result_summary=data.get("result_summary", {}),
            metadata=data.get("metadata", {}),
        )
