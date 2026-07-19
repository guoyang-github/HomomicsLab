"""Cost control and budget enforcement for HomomicsLab.

Aggregates LLM token costs (from LLMClient) and compute costs (from
SkillPerformanceTracker) and enforces per-request and monthly budgets.
Designed for a single-user/tenant deployment; multi-tenant deployments should
key budgets by user_id.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from homomics_lab.config import settings

# Budget caps (formerly HOMOMICS_MONTHLY_BUDGET_USD /
# HOMOMICS_MAX_LLM_COST_PER_REQUEST_USD; defaults kept: no cap).
MONTHLY_BUDGET_USD: Optional[float] = None
MAX_LLM_COST_PER_REQUEST_USD: Optional[float] = None

# Cost caps (formerly HOMOMICS_MONTHLY_BUDGET_USD /
# HOMOMICS_MAX_LLM_COST_PER_REQUEST_USD; defaults kept: no cap).
MONTHLY_BUDGET_USD = None
MAX_LLM_COST_PER_REQUEST_USD = None


@dataclass
class CostSnapshot:
    """Current cost and budget state."""

    llm_cost_usd: float
    compute_cost_usd: float
    total_cost_usd: float
    monthly_budget_usd: Optional[float]
    max_request_cost_usd: Optional[float]
    remaining_monthly_budget_usd: Optional[float]


class CostController:
    """Track and enforce LLM + compute spending budgets."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = settings.data_dir / "homomics_lab_costs.db"
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT,
                    session_id TEXT,
                    project_id TEXT,
                    model TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    cost_usd REAL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_llm_costs_created_at
                    ON llm_costs(created_at)
                """
            )
            conn.commit()

    def record_llm_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Persist an LLM call cost record."""
        self._ensure_llm_cost_columns()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO llm_costs
                (request_id, session_id, project_id, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    session_id,
                    project_id,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost_usd,
                    now,
                ),
            )
            conn.commit()

    def _ensure_llm_cost_columns(self) -> None:
        """Add session/project id columns to legacy llm_costs tables."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("PRAGMA table_info(llm_costs)")
                columns = {row[1] for row in cursor.fetchall()}
                if "session_id" not in columns:
                    conn.execute("ALTER TABLE llm_costs ADD COLUMN session_id TEXT")
                if "project_id" not in columns:
                    conn.execute("ALTER TABLE llm_costs ADD COLUMN project_id TEXT")
                conn.commit()
        except Exception:
            pass

    def get_monthly_llm_cost(self) -> float:
        """Return total LLM cost for the current calendar month."""
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0.0)
                FROM llm_costs
                WHERE created_at >= ?
                """,
                (start.isoformat(),),
            ).fetchone()
        return round(row[0], 6)

    def get_monthly_compute_cost(self) -> float:
        """Return total compute cost for the current calendar month from skill metrics."""
        metrics_db = settings.data_dir / "homomics_lab_metrics.db"
        if not metrics_db.exists():
            return 0.0
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        try:
            with sqlite3.connect(str(metrics_db)) as conn:
                row = conn.execute(
                    """
                    SELECT COALESCE(SUM(estimated_cost_usd), 0.0)
                    FROM skill_executions
                    WHERE timestamp >= ?
                    """,
                    (start.isoformat(),),
                ).fetchone()
            return round(row[0] or 0.0, 6)
        except Exception:
            return 0.0

    def get_snapshot(self) -> CostSnapshot:
        llm = self.get_monthly_llm_cost()
        compute = self.get_monthly_compute_cost()
        total = round(llm + compute, 6)
        budget = MONTHLY_BUDGET_USD
        remaining = round(budget - total, 6) if budget is not None else None
        return CostSnapshot(
            llm_cost_usd=llm,
            compute_cost_usd=compute,
            total_cost_usd=total,
            monthly_budget_usd=budget,
            max_request_cost_usd=MAX_LLM_COST_PER_REQUEST_USD,
            remaining_monthly_budget_usd=remaining,
        )

    def check_request_budget(
        self, estimated_cost_usd: float, cap: Optional[float] = None
    ) -> None:
        """Raise BudgetExceeded if a single LLM request exceeds the per-request cap.

        Also checks monthly budget if configured. The optional ``cap`` argument
        allows callers (e.g. ``LLMRouter``) to enforce a stricter per-request
        limit than the global setting.
        """
        global_cap = MAX_LLM_COST_PER_REQUEST_USD
        caps = [c for c in (cap, global_cap) if c is not None]
        max_request = min(caps) if caps else None
        if max_request is not None and estimated_cost_usd > max_request:
            raise BudgetExceeded(
                f"Estimated request cost ${estimated_cost_usd:.4f} exceeds "
                f"per-request cap ${max_request:.4f}"
            )

        monthly = MONTHLY_BUDGET_USD
        if monthly is not None:
            snapshot = self.get_snapshot()
            if snapshot.remaining_monthly_budget_usd is not None and snapshot.remaining_monthly_budget_usd <= 0:
                raise BudgetExceeded(
                    f"Monthly budget ${monthly:.2f} exhausted. "
                    f"Current spend: ${snapshot.total_cost_usd:.4f}"
                )

    def get_usage_report(self) -> Dict[str, any]:
        snapshot = self.get_snapshot()
        return {
            "llm_cost_usd": snapshot.llm_cost_usd,
            "compute_cost_usd": snapshot.compute_cost_usd,
            "total_cost_usd": snapshot.total_cost_usd,
            "monthly_budget_usd": snapshot.monthly_budget_usd,
            "max_request_cost_usd": snapshot.max_request_cost_usd,
            "remaining_monthly_budget_usd": snapshot.remaining_monthly_budget_usd,
        }


class BudgetExceeded(Exception):
    """Raised when a cost budget is exceeded."""


# Singleton for the process.
_cost_controller: Optional[CostController] = None


def get_cost_controller() -> CostController:
    global _cost_controller
    if _cost_controller is None:
        _cost_controller = CostController()
    return _cost_controller


def reset_cost_controller() -> None:
    global _cost_controller
    _cost_controller = None
