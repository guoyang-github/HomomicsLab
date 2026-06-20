"""Skill performance tracking with GPU/CPU cost analysis.

Tracks execution metrics including:
  - Duration and success rate
  - CPU usage (% and time)
  - GPU usage (% and time, if available)
  - Memory consumption
  - Estimated cost in USD

Usage:
    from homomics_lab.skills.tracker import SkillPerformanceTracker, ResourceSampler

    sampler = ResourceSampler()
    tracker = SkillPerformanceTracker()

    with sampler.sample() as metrics:
        result = await execute_skill(...)

    tracker.record(
        skill_id="scanpy_qc",
        duration_ms=metrics.duration_ms,
        success=True,
        cpu_percent=metrics.cpu_percent,
        memory_mb=metrics.memory_mb,
        gpu_percent=metrics.gpu_percent,
    )
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


@dataclass
class ResourceMetrics:
    """Resource usage snapshot during skill execution."""

    duration_ms: float = 0.0
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    gpu_percent: Optional[float] = None
    gpu_memory_mb: Optional[float] = None


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
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    gpu_percent: Optional[float] = None
    estimated_cost_usd: Optional[float] = None


@dataclass
class CostConfig:
    """Pricing configuration for cost estimation."""

    cpu_hour_usd: float = 0.05  # $0.05 per CPU core-hour
    gpu_hour_usd: float = 2.50  # $2.50 per GPU hour (V100 equivalent)
    memory_gb_hour_usd: float = 0.01  # $0.01 per GB-hour


class ResourceSampler:
    """Sample CPU/GPU/memory usage during code execution.

    Usage:
        sampler = ResourceSampler()
        with sampler.sample() as metrics:
            # ... execute skill ...
            pass
        print(f"CPU: {metrics.cpu_percent}%, Memory: {metrics.memory_mb}MB")
    """

    def __init__(self):
        self._psutil = None
        self._pynvml = None

    def _get_psutil(self):
        if self._psutil is None:
            try:
                import psutil

                self._psutil = psutil
            except ImportError:
                pass
        return self._psutil

    def _get_pynvml(self):
        if self._pynvml is None:
            try:
                import pynvml

                pynvml.nvmlInit()
                self._pynvml = pynvml
            except Exception:
                pass
        return self._pynvml

    @contextmanager
    def sample(self) -> Generator[ResourceMetrics, None, None]:
        """Context manager that samples resources before and after execution."""
        metrics = ResourceMetrics()
        start_time = time.time()

        psutil = self._get_psutil()
        pynvml = self._get_pynvml()

        # Sample before
        cpu_before = None
        mem_before = None
        if psutil:
            cpu_before = psutil.cpu_percent(interval=None)
            mem_before = psutil.virtual_memory().used / (1024 ** 2)  # MB

        gpu_before = None
        if pynvml:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_before = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            except Exception:
                pass

        try:
            yield metrics
        finally:
            end_time = time.time()
            metrics.duration_ms = (end_time - start_time) * 1000

            # Sample after
            if psutil:
                cpu_after = psutil.cpu_percent(interval=None)
                mem_after = psutil.virtual_memory().used / (1024 ** 2)

                # Use average of before/after as rough estimate
                if cpu_before is not None:
                    metrics.cpu_percent = round((cpu_before + cpu_after) / 2, 2)
                metrics.memory_mb = round(max(0, mem_after - mem_before), 2)

            if pynvml and gpu_before is not None:
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_after = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                    metrics.gpu_percent = round((gpu_before + gpu_after) / 2, 2)
                except Exception:
                    pass

    def has_gpu(self) -> bool:
        """Check if GPU monitoring is available."""
        return self._get_pynvml() is not None

    def has_cpu_monitoring(self) -> bool:
        """Check if CPU monitoring is available."""
        return self._get_psutil() is not None


class SkillPerformanceTracker:
    """Track and analyze skill execution performance with cost estimation."""

    def __init__(self, db_path: Path = None, cost_config: CostConfig = None):
        self.db_path = db_path or Path("./homomics_lab_metrics.db")
        self.cost_config = cost_config or CostConfig()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database with migration support."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    success INTEGER NOT NULL,
                    output_size INTEGER NOT NULL DEFAULT 0,
                    executor_type TEXT NOT NULL DEFAULT 'local',
                    error_message TEXT,
                    metadata TEXT,
                    cpu_percent REAL,
                    memory_mb REAL,
                    gpu_percent REAL,
                    estimated_cost_usd REAL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_skill_id ON skill_executions(skill_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp ON skill_executions(timestamp)
                """
            )

            # Migration: add new columns if they don't exist
            self._migrate_add_column(conn, "cpu_percent", "REAL")
            self._migrate_add_column(conn, "memory_mb", "REAL")
            self._migrate_add_column(conn, "gpu_percent", "REAL")
            self._migrate_add_column(conn, "estimated_cost_usd", "REAL")

            conn.commit()

    def _migrate_add_column(
        self, conn: sqlite3.Connection, column: str, col_type: str
    ) -> None:
        """Add a column if it doesn't already exist."""
        cursor = conn.execute("PRAGMA table_info(skill_executions)")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            conn.execute(
                f"ALTER TABLE skill_executions ADD COLUMN {column} {col_type}"
            )

    def _estimate_cost(
        self,
        duration_ms: float,
        cpu_percent: Optional[float],
        gpu_percent: Optional[float],
        memory_mb: Optional[float],
    ) -> Optional[float]:
        """Estimate execution cost in USD.

        Formula:
          cost = (cpu_hours * cpu_rate) + (gpu_hours * gpu_rate) + (mem_gb_hours * mem_rate)
        """
        if duration_ms <= 0:
            return 0.0

        hours = duration_ms / (1000 * 3600)
        cost = 0.0

        # Assume 2 CPU cores used on average if not monitored
        cpu_cores = 2
        if cpu_percent is not None:
            cost += hours * (cpu_percent / 100) * cpu_cores * self.cost_config.cpu_hour_usd

        if gpu_percent is not None:
            cost += hours * (gpu_percent / 100) * self.cost_config.gpu_hour_usd

        if memory_mb is not None:
            cost += hours * (memory_mb / 1024) * self.cost_config.memory_gb_hour_usd

        return round(cost, 6) if cost > 0 else None

    def record(
        self,
        skill_id: str,
        duration_ms: float,
        success: bool,
        output_size: int = 0,
        executor_type: str = "local",
        error_message: str = None,
        metadata: Dict[str, Any] = None,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        gpu_percent: Optional[float] = None,
    ) -> None:
        """Record a skill execution with resource metrics."""
        timestamp = datetime.now(timezone.utc).isoformat()
        cost = self._estimate_cost(duration_ms, cpu_percent, gpu_percent, memory_mb)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO skill_executions
                (skill_id, timestamp, duration_ms, success, output_size, executor_type,
                 error_message, metadata, cpu_percent, memory_mb, gpu_percent, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    cpu_percent,
                    memory_mb,
                    gpu_percent,
                    cost,
                ),
            )
            conn.commit()

    def get_stats(self, skill_id: str) -> Dict[str, Any]:
        """Get aggregate statistics for a skill including resource usage."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(duration_ms) as avg_duration,
                    MIN(duration_ms) as min_duration,
                    MAX(duration_ms) as max_duration,
                    AVG(output_size) as avg_output_size,
                    AVG(cpu_percent) as avg_cpu,
                    AVG(memory_mb) as avg_mem,
                    AVG(gpu_percent) as avg_gpu,
                    SUM(estimated_cost_usd) as total_cost
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
                "avg_cpu_percent": None,
                "avg_memory_mb": None,
                "avg_gpu_percent": None,
                "total_cost_usd": 0.0,
            }

        total, successes, avg_dur, min_dur, max_dur, avg_out, avg_cpu, avg_mem, avg_gpu, total_cost = row
        return {
            "skill_id": skill_id,
            "total_executions": total,
            "success_rate": (successes / total * 100) if total > 0 else 0.0,
            "avg_duration_ms": round(avg_dur, 2) if avg_dur else 0.0,
            "min_duration_ms": round(min_dur, 2) if min_dur else 0.0,
            "max_duration_ms": round(max_dur, 2) if max_dur else 0.0,
            "avg_output_size": round(avg_out, 2) if avg_out else 0.0,
            "avg_cpu_percent": round(avg_cpu, 2) if avg_cpu is not None else None,
            "avg_memory_mb": round(avg_mem, 2) if avg_mem is not None else None,
            "avg_gpu_percent": round(avg_gpu, 2) if avg_gpu is not None else None,
            "total_cost_usd": round(total_cost, 6) if total_cost else 0.0,
        }

    def get_recent_executions(
        self,
        skill_id: str = None,
        limit: int = 100,
    ) -> List[ExecutionRecord]:
        """Get recent execution records with resource metrics."""
        with sqlite3.connect(str(self.db_path)) as conn:
            if skill_id:
                rows = conn.execute(
                    """
                    SELECT skill_id, timestamp, duration_ms, success, output_size,
                           executor_type, error_message, metadata,
                           cpu_percent, memory_mb, gpu_percent, estimated_cost_usd
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
                           executor_type, error_message, metadata,
                           cpu_percent, memory_mb, gpu_percent, estimated_cost_usd
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
                cpu_percent=r[8],
                memory_mb=r[9],
                gpu_percent=r[10],
                estimated_cost_usd=r[11],
            )
            for r in rows
        ]

    def get_top_skills(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top skills by execution count with cost summary."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT
                    skill_id,
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(duration_ms) as avg_duration,
                    SUM(estimated_cost_usd) as total_cost
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
                "total_cost_usd": round(r[4], 6) if r[4] else 0.0,
            }
            for r in rows
        ]

    def compare_skills(
        self,
        skill_a: str,
        skill_b: str,
    ) -> Dict[str, Any]:
        """Compare two skills by performance and cost metrics."""
        stats_a = self.get_stats(skill_a)
        stats_b = self.get_stats(skill_b)

        return {
            "skill_a": stats_a,
            "skill_b": stats_b,
            "comparison": {
                "success_rate_diff": round(stats_a["success_rate"] - stats_b["success_rate"], 2),
                "avg_duration_diff_ms": round(stats_a["avg_duration_ms"] - stats_b["avg_duration_ms"], 2),
                "total_executions_diff": stats_a["total_executions"] - stats_b["total_executions"],
                "total_cost_diff_usd": round(
                    (stats_a.get("total_cost_usd", 0) or 0) - (stats_b.get("total_cost_usd", 0) or 0),
                    6,
                ),
            },
        }

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get overall cost summary across all skills."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total_executions,
                    SUM(estimated_cost_usd) as total_cost,
                    AVG(estimated_cost_usd) as avg_cost_per_run
                FROM skill_executions
                """
            ).fetchone()

        total, total_cost, avg_cost = row
        return {
            "total_executions": total,
            "total_cost_usd": round(total_cost, 6) if total_cost else 0.0,
            "avg_cost_per_run_usd": round(avg_cost, 6) if avg_cost else 0.0,
        }
