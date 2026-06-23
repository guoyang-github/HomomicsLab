"""WorkspaceManager — persistent project-level working directory management.

Each project gets its own persistent workspace under workspaces/{project_id}/.
Skills execute within this workspace, and intermediate results are preserved
across analysis steps for reproducibility and inspection.

Directory layout:
  workspaces/{project_id}/
    ├── data/               # Original/raw data (read-only protection)
    ├── intermediate/       # Step-to-step artifacts
    ├── outputs/            # Final deliverables (figures, reports, tables)
    ├── logs/               # Execution logs
    └── .metadata/          # State, manifest, lineage, snapshots
"""

import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from homomics_lab.workspace.lineage import LineageEdge, LineageGraph, LineageNode
from homomics_lab.stability.version_locker import VersionLocker, VersionLock


@dataclass
class ArtifactRecord:
    """Record of a file produced during analysis."""

    artifact_id: str
    task_id: str
    artifact_type: str  # "data" | "intermediate" | "output"
    relative_path: str
    checksum: str
    source_task: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkspaceSnapshot:
    """A point-in-time snapshot of the workspace."""

    snapshot_id: str
    label: str
    created_at: str
    file_manifest: List[Dict[str, Any]]


class WorkspaceManager:
    """Manages a persistent working directory for a single project.

    Usage:
        ws = WorkspaceManager(base_dir=Path("./data"), project_id="proj_1")
        input_path = ws.get_path("data/raw.h5ad")
        output_path = ws.register_artifact(
            task_id="qc_1",
            artifact_type="intermediate",
            filename="qc_filtered.h5ad",
            source_task="load_1",
        )
    """

    DATA_SUBDIR = "data"
    INTERMEDIATE_SUBDIR = "intermediate"
    OUTPUTS_SUBDIR = "outputs"
    LOGS_SUBDIR = "logs"
    METADATA_SUBDIR = ".metadata"

    def __init__(self, base_dir: Union[str, Path], project_id: str):
        self.base_dir = Path(base_dir)
        self.project_id = project_id
        self.workspace_dir = self.base_dir / "workspaces" / project_id
        self._ensure_structure()
        self._init_metadata_db()
        self._version_locker = VersionLocker(self.workspace_dir)

    # ─────────────────────────────────────────
    # Structure & paths
    # ─────────────────────────────────────────

    def _ensure_structure(self) -> None:
        """Create workspace directories if they don't exist."""
        for subdir in (
            self.DATA_SUBDIR,
            self.INTERMEDIATE_SUBDIR,
            self.OUTPUTS_SUBDIR,
            self.LOGS_SUBDIR,
            self.METADATA_SUBDIR,
        ):
            (self.workspace_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _init_metadata_db(self) -> None:
        """Initialize SQLite metadata database."""
        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    checksum TEXT,
                    source_task TEXT,
                    created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    manifest TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type)"
            )
            conn.commit()

    def get_path(self, relative_path: Union[str, Path]) -> Path:
        """Resolve a relative path to an absolute workspace path.

        Supports the workspace:// protocol:
            ws.get_path("workspace://intermediate/qc.h5ad")
            → /base/workspaces/{project_id}/intermediate/qc.h5ad

        Plain relative paths are resolved against the workspace root:
            ws.get_path("intermediate/qc.h5ad")
            → /base/workspaces/{project_id}/intermediate/qc.h5ad
        """
        rel = str(relative_path)
        if rel.startswith("workspace://"):
            rel = rel.replace("workspace://", "")
            # Prevent escaping workspace via ../
            resolved = (self.workspace_dir / rel).resolve()
            if not str(resolved).startswith(str(self.workspace_dir.resolve())):
                raise ValueError(f"Path escapes workspace: {relative_path}")
            return resolved

        return (self.workspace_dir / rel).resolve()

    def get_data_path(self, filename: str) -> Path:
        """Get path in the data/ subdirectory."""
        return self.workspace_dir / self.DATA_SUBDIR / filename

    def get_intermediate_path(self, filename: str) -> Path:
        """Get path in the intermediate/ subdirectory."""
        return self.workspace_dir / self.INTERMEDIATE_SUBDIR / filename

    def get_outputs_path(self, filename: str) -> Path:
        """Get path in the outputs/ subdirectory."""
        return self.workspace_dir / self.OUTPUTS_SUBDIR / filename

    def get_logs_path(self, filename: str) -> Path:
        """Get path in the logs/ subdirectory."""
        return self.workspace_dir / self.LOGS_SUBDIR / filename

    # ─────────────────────────────────────────
    # Artifact registration & lineage
    # ─────────────────────────────────────────

    def register_artifact(
        self,
        task_id: str,
        artifact_type: str,
        filename: str,
        source_task: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Register a file as a tracked artifact and record its lineage.

        Returns:
            The absolute path where the artifact should be written.
        """
        if artifact_type not in ("data", "intermediate", "output"):
            raise ValueError(f"Invalid artifact_type: {artifact_type}")

        artifact_id = str(uuid4())
        relative_path = f"{artifact_type}/{filename}"
        abs_path = self.workspace_dir / relative_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # Compute checksum if file already exists
        checksum = ""
        if abs_path.exists():
            checksum = self._compute_checksum(abs_path)

        record = ArtifactRecord(
            artifact_id=artifact_id,
            task_id=task_id,
            artifact_type=artifact_type,
            relative_path=relative_path,
            checksum=checksum,
            source_task=source_task,
            metadata=metadata or {},
        )
        self._persist_artifact(record)
        return abs_path

    def update_artifact_checksum(self, relative_path: str) -> None:
        """Update the checksum of an artifact after it has been written."""
        abs_path = self.workspace_dir / relative_path
        if not abs_path.exists():
            return
        checksum = self._compute_checksum(abs_path)
        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "UPDATE artifacts SET checksum = ? WHERE relative_path = ?",
                (checksum, relative_path),
            )
            conn.commit()

    def _persist_artifact(self, record: ArtifactRecord) -> None:
        """Persist artifact record to SQLite."""
        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts
                (artifact_id, task_id, artifact_type, relative_path, checksum,
                 source_task, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.task_id,
                    record.artifact_type,
                    record.relative_path,
                    record.checksum,
                    record.source_task,
                    record.created_at,
                    json.dumps(record.metadata, ensure_ascii=False),
                ),
            )
            conn.commit()

    @staticmethod
    def _compute_checksum(file_path: Path) -> str:
        """Compute SHA-256 checksum of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def list_artifacts(
        self,
        artifact_type: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> List[ArtifactRecord]:
        """List tracked artifacts, optionally filtered."""
        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        query = "SELECT * FROM artifacts WHERE 1=1"
        params: List[Any] = []
        if artifact_type:
            query += " AND artifact_type = ?"
            params.append(artifact_type)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        query += " ORDER BY created_at"

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        return [
            ArtifactRecord(
                artifact_id=r["artifact_id"],
                task_id=r["task_id"],
                artifact_type=r["artifact_type"],
                relative_path=r["relative_path"],
                checksum=r["checksum"],
                source_task=r["source_task"],
                created_at=r["created_at"],
                metadata=json.loads(r["metadata"]),
            )
            for r in rows
        ]

    def delete_artifacts_by_figure_id(self, figure_id: str) -> int:
        """Delete all tracked files and database records for a figure."""
        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE metadata LIKE ?",
                (f'%"figure_id": "{figure_id}"%',),
            ).fetchall()

        deleted_files = 0
        for row in rows:
            metadata = json.loads(row["metadata"])
            if metadata.get("figure_id") != figure_id:
                continue

            for fmt_path in metadata.get("formats", {}).values():
                target = self.workspace_dir / fmt_path
                if target.exists() and target.is_file():
                    target.unlink()
                    deleted_files += 1

            abs_path = self.workspace_dir / row["relative_path"]
            if abs_path.exists() and abs_path.is_file():
                abs_path.unlink()
                deleted_files += 1

            with sqlite3.connect(str(db_path)) as conn:
                conn.execute(
                    "DELETE FROM artifacts WHERE artifact_id = ?",
                    (row["artifact_id"],),
                )
                conn.commit()

        return deleted_files

    # ─────────────────────────────────────────
    # Snapshots
    # ─────────────────────────────────────────

    def snapshot(self, label: str) -> str:
        """Create a point-in-time snapshot of the workspace.

        Returns:
            snapshot_id
        """
        snapshot_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Build file manifest
        manifest = []
        for root, _dirs, files in os.walk(self.workspace_dir):
            for f in files:
                fp = Path(root) / f
                if self.METADATA_SUBDIR in str(fp.relative_to(self.workspace_dir)):
                    continue
                rel = str(fp.relative_to(self.workspace_dir))
                manifest.append(
                    {
                        "path": rel,
                        "checksum": self._compute_checksum(fp),
                        "size": fp.stat().st_size,
                    }
                )

        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                INSERT INTO snapshots (snapshot_id, label, created_at, manifest)
                VALUES (?, ?, ?, ?)
                """,
                (snapshot_id, label, created_at, json.dumps(manifest)),
            )
            conn.commit()

        # Copy files into the snapshot directory for true restore capability.
        snapshot_files_dir = (
            self.workspace_dir
            / self.METADATA_SUBDIR
            / "snapshots"
            / snapshot_id
            / "files"
        )
        for root, _dirs, files in os.walk(self.workspace_dir):
            for f in files:
                fp = Path(root) / f
                if self.METADATA_SUBDIR in str(fp.relative_to(self.workspace_dir)):
                    continue
                rel = fp.relative_to(self.workspace_dir)
                dest = snapshot_files_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fp, dest)

        return snapshot_id

    def list_snapshots(self) -> List[WorkspaceSnapshot]:
        """List all snapshots."""
        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM snapshots ORDER BY created_at"
            ).fetchall()

        return [
            WorkspaceSnapshot(
                snapshot_id=r["snapshot_id"],
                label=r["label"],
                created_at=r["created_at"],
                file_manifest=json.loads(r["manifest"]),
            )
            for r in rows
        ]

    def restore(self, snapshot_id: str) -> None:
        """Restore workspace to a snapshot.

        WARNING: This will delete any files created after the snapshot.
        """
        db_path = self.workspace_dir / self.METADATA_SUBDIR / "workspace.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Snapshot not found: {snapshot_id}")

            _manifest = json.loads(row["manifest"])

        # Remove all files except metadata dir
        for subdir in (
            self.DATA_SUBDIR,
            self.INTERMEDIATE_SUBDIR,
            self.OUTPUTS_SUBDIR,
            self.LOGS_SUBDIR,
        ):
            path = self.workspace_dir / subdir
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)

        # If a full file copy was saved, restore it; otherwise fall back to
        # the manifest-only behaviour and let the caller recreate files.
        snapshot_files_dir = (
            self.workspace_dir
            / self.METADATA_SUBDIR
            / "snapshots"
            / snapshot_id
            / "files"
        )
        if snapshot_files_dir.exists():
            for root, _dirs, files in os.walk(snapshot_files_dir):
                for f in files:
                    fp = Path(root) / f
                    rel = fp.relative_to(snapshot_files_dir)
                    dest = self.workspace_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(fp, dest)
            return

        # Restore from manifest only (MVP fallback).

    # ─────────────────────────────────────────
    # Data lineage
    # ─────────────────────────────────────────

    def build_lineage_graph(self) -> LineageGraph:
        """Build a data lineage graph from registered artifacts."""
        artifacts = self.list_artifacts()
        nodes: Dict[str, LineageNode] = {}
        edges: List[LineageEdge] = []

        for art in artifacts:
            node_id = art.artifact_id
            nodes[node_id] = LineageNode(
                node_id=node_id,
                path=art.relative_path,
                type=art.artifact_type,
                checksum=art.checksum,
                created_by_task=art.task_id,
                created_at=art.created_at,
            )
            if art.source_task:
                # Find the artifact produced by source_task
                source_artifacts = [
                    a for a in artifacts if a.task_id == art.source_task
                ]
                for src in source_artifacts:
                    edges.append(
                        LineageEdge(
                            from_node=src.artifact_id,
                            to_node=node_id,
                            transform_type="skill",
                            transform_id=art.task_id,
                        )
                    )

        return LineageGraph(nodes=list(nodes.values()), edges=edges)

    # ─────────────────────────────────────────
    # Read-only protection for data/
    # ─────────────────────────────────────────

    def protect_data(self, path: Union[str, Path]) -> None:
        """Mark a file in data/ as read-only."""
        abs_path = self.get_path(path)
        if not str(abs_path).startswith(str(self.workspace_dir / self.DATA_SUBDIR)):
            raise ValueError("Can only protect files in data/")
        abs_path.chmod(0o444)

    # ─────────────────────────────────────────
    # Version locking
    # ─────────────────────────────────────────

    def lock_versions(self, skill_registry) -> VersionLock:
        """Create a version lock for the current project state."""
        return self._version_locker.lock_project(self.project_id, skill_registry)

    def verify_versions(self, skill_registry):
        """Verify current state against the stored lock."""
        return self._version_locker.verify(skill_registry)

    def __repr__(self) -> str:
        return f"WorkspaceManager(project_id={self.project_id}, dir={self.workspace_dir})"
