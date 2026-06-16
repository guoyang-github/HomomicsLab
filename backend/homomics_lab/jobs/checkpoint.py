"""Job checkpoint storage for resume/rollback support.

A checkpoint captures the state of a job at a specific task boundary. It can be
used to resume a long-running analysis from the latest successful phase, or to
roll back to a known-good state after a partial failure.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings


@dataclass
class Checkpoint:
    """A recorded checkpoint for a job/task boundary."""

    checkpoint_id: str
    job_id: str
    task_id: str
    phase: Optional[str]
    status: str  # "success" | "failure" | "manual"
    payload: Dict[str, Any]
    created_at: datetime


class CheckpointRepository:
    """SQLite-backed checkpoint repository."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path(settings.data_dir) / "checkpoints.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    phase TEXT,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_checkpoints_job_task
                    ON checkpoints(job_id, task_id)
                """
            )
            conn.commit()

    def record(
        self,
        checkpoint_id: str,
        job_id: str,
        task_id: str,
        payload: Dict[str, Any],
        phase: Optional[str] = None,
        status: str = "success",
    ) -> Checkpoint:
        """Record a new checkpoint."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO checkpoints
                (checkpoint_id, job_id, task_id, phase, status, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_id,
                    job_id,
                    task_id,
                    phase,
                    status,
                    json.dumps(payload, default=str),
                    now,
                ),
            )
            conn.commit()
        return Checkpoint(
            checkpoint_id=checkpoint_id,
            job_id=job_id,
            task_id=task_id,
            phase=phase,
            status=status,
            payload=payload,
            created_at=datetime.fromisoformat(now),
        )

    def get_latest(self, job_id: str, status: Optional[str] = None) -> Optional[Checkpoint]:
        """Return the most recent checkpoint for a job, optionally filtered by status."""
        query = "SELECT * FROM checkpoints WHERE job_id = ?"
        params: List[Any] = [job_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT 1"

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(query, params).fetchone()
        if row is None:
            return None
        return self._row_to_checkpoint(row)

    def list_by_job(
        self,
        job_id: str,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Checkpoint]:
        """List checkpoints for a job, optionally filtered by task and status."""
        query = "SELECT * FROM checkpoints WHERE job_id = ?"
        params: List[Any] = [job_id]
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_checkpoint(row) for row in rows]

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Fetch a single checkpoint by ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_checkpoint(row)

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint. Returns True if it existed."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    @staticmethod
    def _row_to_checkpoint(row: sqlite3.Row) -> Checkpoint:
        return Checkpoint(
            checkpoint_id=row["checkpoint_id"],
            job_id=row["job_id"],
            task_id=row["task_id"],
            phase=row["phase"],
            status=row["status"],
            payload=json.loads(row["payload"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
