"""Skill performance tracking and metrics storage."""

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionRecord:
    """A single skill execution record."""

    skill_id: str
    timestamp: str
    duration_ms: float
    success: bool
    output_size: int
    executor_type: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SkillPerformanceTracker:
    """Track and analyze skill execution performance."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("./homomics_lab_metrics.db")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    success INTEGER NOT NULL,
                    output_size INTEGER NOT NULL DEFAULT 0,
                    executor_type TEXT NOT NULL DEFAULT 'local',
                    error_message TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_skill_id ON skill_executions(skill_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON skill_executions(timestamp)
            """)
            conn.commit()

    def record(
        self,
        skill_id: str,
        duration_ms: float,
        success: bool,
        output_size: int = 0,
        executor_type: str = "local",
        error_message: str = None,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """Record a skill execution."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO skill_executions
                (skill_id, timestamp, duration_ms, success, output_size, executor_type, error_message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill_id,
                    timestamp,
                    duration_ms,
                    1 if success else 0,
                    output_size,
                    executor_type,
                    error_message,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()

    def get_stats(self, skill_id: str) -> Dict[str, Any]:
        """Get aggregate statistics for a skill."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(duration_ms) as avg_duration,
                    MIN(duration_ms) as min_duration,
                    MAX(duration_ms) as max_duration,
                    AVG(output_size) as avg_output_size
                FROM skill_executions
                WHERE skill_id = ?
                """,
                (skill_id,),
            ).fetchone()

        if not row or row[0] == 0:
            return {
                "skill_id": skill_id,
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "avg_output_size": 0.0,
            }

        total, successes, avg_dur, min_dur, max_dur, avg_out = row
        return {
            "skill_id": skill_id,
            "total_executions": total,
            "success_rate": (successes / total * 100) if total > 0 else 0.0,
            "avg_duration_ms": round(avg_dur, 2) if avg_dur else 0.0,
            "min_duration_ms": round(min_dur, 2) if min_dur else 0.0,
            "max_duration_ms": round(max_dur, 2) if max_dur else 0.0,
            "avg_output_size": round(avg_out, 2) if avg_out else 0.0,
        }

    def get_recent_executions(
        self,
        skill_id: str = None,
        limit: int = 100,
    ) -> List[ExecutionRecord]:
        """Get recent execution records."""
        with sqlite3.connect(str(self.db_path)) as conn:
            if skill_id:
                rows = conn.execute(
                    """
                    SELECT skill_id, timestamp, duration_ms, success, output_size,
                           executor_type, error_message, metadata
                    FROM skill_executions
                    WHERE skill_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (skill_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT skill_id, timestamp, duration_ms, success, output_size,
                           executor_type, error_message, metadata
                    FROM skill_executions
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [
            ExecutionRecord(
                skill_id=r[0],
                timestamp=r[1],
                duration_ms=r[2],
                success=bool(r[3]),
                output_size=r[4],
                executor_type=r[5],
                error_message=r[6],
                metadata=json.loads(r[7]) if r[7] else None,
            )
            for r in rows
        ]

    def get_top_skills(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top skills by execution count."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT
                    skill_id,
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(duration_ms) as avg_duration
                FROM skill_executions
                GROUP BY skill_id
                ORDER BY total DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "skill_id": r[0],
                "total_executions": r[1],
                "success_rate": round((r[2] / r[1] * 100), 2) if r[1] > 0 else 0.0,
                "avg_duration_ms": round(r[3], 2) if r[3] else 0.0,
            }
            for r in rows
        ]

    def compare_skills(
        self,
        skill_a: str,
        skill_b: str,
    ) -> Dict[str, Any]:
        """Compare two skills by performance metrics."""
        stats_a = self.get_stats(skill_a)
        stats_b = self.get_stats(skill_b)

        return {
            "skill_a": stats_a,
            "skill_b": stats_b,
            "comparison": {
                "success_rate_diff": round(stats_a["success_rate"] - stats_b["success_rate"], 2),
                "avg_duration_diff_ms": round(stats_a["avg_duration_ms"] - stats_b["avg_duration_ms"], 2),
                "total_executions_diff": stats_a["total_executions"] - stats_b["total_executions"],
            },
        }
