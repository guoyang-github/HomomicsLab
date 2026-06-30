"""Execution feedback store for ranking memories and capabilities.

Feedback is the fuel for the system's self-improvement loop.  Every time a memory
snippet or a capability (skill/tool/SOP) is used in a turn, the outcome is recorded
and distilled into:

- ``success_rate``: fraction of positive outcomes.
- ``avg_rating``: optional explicit human rating (1–5).
- ``usage_count``: how many times the item has been involved.

These signals are consumed by ``MemoryBackend`` and ``CapabilityIndex`` to rerank
retrieval results so that historically useful items surface first.
"""

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class FeedbackOutcome(str, Enum):
    """Discrete outcome of using a memory or capability."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"

    @property
    def score(self) -> float:
        return {"success": 1.0, "partial": 0.5, "failure": 0.0}[self.value]


@dataclass
class ExecutionFeedback:
    """A single feedback record."""

    target_type: str  # "memory" | "skill" | "tool" | "sop" | "experiment" | "data_source"
    target_id: str
    outcome: FeedbackOutcome
    project_id: Optional[str] = None
    rating: Optional[int] = None  # 1-5, optional explicit rating
    comment: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class FeedbackStats:
    """Aggregated feedback statistics for an item."""

    target_type: str
    target_id: str
    success_rate: float
    avg_rating: Optional[float]
    usage_count: int
    last_feedback_at: Optional[str]


class FeedbackStore(ABC):
    """Abstract store for execution feedback."""

    @abstractmethod
    def record(self, feedback: ExecutionFeedback) -> None:
        """Persist a feedback record."""

    @abstractmethod
    def get_stats(
        self,
        target_type: str,
        target_id: str,
        project_id: Optional[str] = None,
    ) -> FeedbackStats:
        """Return aggregated statistics for an item."""

    @abstractmethod
    def list_recent(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ExecutionFeedback]:
        """Return recent feedback records, optionally filtered."""


class SQLiteFeedbackStore(FeedbackStore):
    """SQLite-backed feedback store."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path("./data/feedback.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_feedback (
                id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                project_id TEXT,
                outcome TEXT NOT NULL,
                rating INTEGER,
                comment TEXT,
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_target ON execution_feedback(target_type, target_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_project ON execution_feedback(project_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_created ON execution_feedback(created_at)"
        )
        conn.commit()

    def record(self, feedback: ExecutionFeedback) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO execution_feedback
            (id, target_type, target_id, project_id, outcome, rating, comment, context_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback.id,
                feedback.target_type,
                feedback.target_id,
                feedback.project_id,
                feedback.outcome.value,
                feedback.rating,
                feedback.comment,
                json.dumps(feedback.context, ensure_ascii=False),
                feedback.created_at,
            ),
        )
        conn.commit()

    def get_stats(
        self,
        target_type: str,
        target_id: str,
        project_id: Optional[str] = None,
    ) -> FeedbackStats:
        conn = self._get_conn()
        conditions = ["target_type = ?", "target_id = ?"]
        params: List[Any] = [target_type, target_id]
        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        where = "WHERE " + " AND ".join(conditions)

        row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS usage_count,
                AVG(CASE outcome WHEN 'success' THEN 1.0 WHEN 'partial' THEN 0.5 ELSE 0.0 END) AS success_rate,
                AVG(rating) AS avg_rating,
                MAX(created_at) AS last_feedback_at
            FROM execution_feedback
            {where}
            """,
            params,
        ).fetchone()

        return FeedbackStats(
            target_type=target_type,
            target_id=target_id,
            success_rate=row["success_rate"] if row["success_rate"] is not None else 0.5,
            avg_rating=row["avg_rating"],
            usage_count=row["usage_count"] or 0,
            last_feedback_at=row["last_feedback_at"],
        )

    def list_recent(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ExecutionFeedback]:
        conditions: List[str] = []
        params: List[Any] = []
        if target_type is not None:
            conditions.append("target_type = ?")
            params.append(target_type)
        if target_id is not None:
            conditions.append("target_id = ?")
            params.append(target_id)
        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        conn = self._get_conn()
        rows = conn.execute(
            f"""
            SELECT * FROM execution_feedback
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()

        return [
            ExecutionFeedback(
                id=r["id"],
                target_type=r["target_type"],
                target_id=r["target_id"],
                project_id=r["project_id"],
                outcome=FeedbackOutcome(r["outcome"]),
                rating=r["rating"],
                comment=r["comment"],
                context=json.loads(r["context_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
