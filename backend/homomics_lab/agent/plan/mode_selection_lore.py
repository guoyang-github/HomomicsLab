"""Persistent experience table for plan-level execution-mode selection.

The lore stores a lightweight, incrementally-updated histogram of
``(intent_features -> execution_mode)`` observations produced by
``evaluation/mode_benchmark.py`` and real plan executions.  ``ModeSelector``
queries the table as a prior before falling back to its rule-based heuristic.

Storage is intentionally separate from CBKB: mode selection is a structured
counting problem rather than a graph/semantic-knowledge problem, so a small
SQLite table keeps the schema and queries simple.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from homomics_lab.agent.plan.models import PlanResult
from homomics_lab.config import settings

VALID_EXECUTION_MODES = ("auto", "fixed_pipeline", "codeact")


@dataclass(frozen=True)
class IntentFeatures:
    """Stable, hashable features extracted from a ``PlanResult``.

    The key is intentionally lossy: it collapses plans with the same domain,
    intent, phase count and required skill set so that historical observations
    can generalise across similar requests.
    """

    domain: str
    phase_count: int
    top_intent: str
    required_skills: Tuple[Optional[str], ...]

    def key(self) -> str:
        """Return a canonical string key for lookup/storage."""
        return json.dumps(
            {
                "domain": self.domain,
                "phase_count": self.phase_count,
                "top_intent": self.top_intent,
                "required_skills": list(self.required_skills),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def from_plan(cls, plan: PlanResult) -> "IntentFeatures":
        """Build features from a plan result.

        Domain and top_intent are derived from the reproducibility context when
        available, otherwise from the strategy name, so that synthetic plans
        (which have no intent object attached) still produce a stable key.
        """
        ctx = plan.reproducibility_context or {}
        intent = ctx.get("intent") if isinstance(ctx, dict) else None
        domain = intent or plan.strategy_name or "unknown"
        return cls(
            domain=domain,
            phase_count=len(plan.phases),
            top_intent=intent or plan.strategy_name or "unknown",
            required_skills=tuple(
                p.selected_skill.id if p.selected_skill is not None else None
                for p in plan.phases
            ),
        )


class ModeSelectionLore:
    """Histogram-backed prior for ``ModeSelector``."""

    DB_NAME = "mode_selection_lore.db"

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = (
            db_path
            if db_path is not None
            else settings.data_dir / ".metadata" / self.DB_NAME
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS mode_selection_lore (
                    feature_key TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    phase_count INTEGER NOT NULL,
                    top_intent TEXT NOT NULL,
                    auto_count REAL NOT NULL DEFAULT 0,
                    fixed_pipeline_count REAL NOT NULL DEFAULT 0,
                    codeact_count REAL NOT NULL DEFAULT 0,
                    total_weight REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_msl_domain
                    ON mode_selection_lore(domain);
                CREATE INDEX IF NOT EXISTS idx_msl_top_intent
                    ON mode_selection_lore(top_intent);
                CREATE INDEX IF NOT EXISTS idx_msl_updated
                    ON mode_selection_lore(updated_at);
                """
            )
            # Migration: older lore files used a shortened ``fixed_count`` column.
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(mode_selection_lore)"
                ).fetchall()
            }
            if "fixed_pipeline_count" not in columns:
                conn.execute(
                    "ALTER TABLE mode_selection_lore "
                    "ADD COLUMN fixed_pipeline_count REAL NOT NULL DEFAULT 0"
                )
            if "fixed_count" in columns and "fixed_pipeline_count" in columns:
                conn.execute(
                    "UPDATE mode_selection_lore "
                    "SET fixed_pipeline_count = fixed_count "
                    "WHERE fixed_pipeline_count = 0"
                )
                conn.execute("ALTER TABLE mode_selection_lore DROP COLUMN fixed_count")

    def record(
        self,
        features: IntentFeatures,
        mode: str,
        outcome_score: float = 1.0,
    ) -> None:
        """Increment the observed count for ``features -> mode``.

        ``outcome_score`` is the weight of the observation (e.g. a win margin
        or a composite quality score).  It is added to the matching mode bin
        and to the total weight, giving a simple incremental weighted average.
        """
        if mode not in VALID_EXECUTION_MODES:
            raise ValueError(f"Invalid execution mode: {mode!r}")
        if outcome_score < 0:
            raise ValueError("outcome_score must be non-negative")

        mode_column = f"{mode}_count"
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                f"""
                INSERT INTO mode_selection_lore
                    (feature_key, domain, phase_count, top_intent,
                     {mode_column}, total_weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(feature_key) DO UPDATE SET
                    {mode_column} = {mode_column} + excluded.{mode_column},
                    total_weight = total_weight + excluded.total_weight,
                    updated_at = excluded.updated_at
                """,
                (
                    features.key(),
                    features.domain,
                    features.phase_count,
                    features.top_intent,
                    outcome_score,
                    outcome_score,
                    now,
                ),
            )

    def get_recommendation(
        self,
        features: IntentFeatures,
        min_samples: float = 3.0,
        confidence_threshold: float = 0.7,
    ) -> Tuple[Optional[str], float]:
        """Return the historically-best mode and its confidence.

        Confidence is the fraction of total observation weight allocated to the
        winning mode.  If there is no record, or the record has too little
        weight, or the winning confidence is below ``confidence_threshold``,
        returns ``(None, confidence)`` so the caller can fall back to a
        heuristic.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT auto_count, fixed_pipeline_count, codeact_count, total_weight
                FROM mode_selection_lore
                WHERE feature_key = ?
                """,
                (features.key(),),
            ).fetchone()

        if row is None:
            return None, 0.0

        counts = dict(zip(VALID_EXECUTION_MODES, row[:3]))
        total_weight = row[3] or 0.0
        if total_weight < min_samples:
            return None, 0.0

        best_mode = max(counts, key=lambda m: counts[m])
        confidence = counts[best_mode] / total_weight
        if confidence < confidence_threshold:
            return None, confidence
        return best_mode, confidence

    def get_stats(self) -> dict:
        """Return aggregate statistics for introspection/testing."""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM mode_selection_lore"
            ).fetchone()[0]
            total_weight = conn.execute(
                "SELECT COALESCE(SUM(total_weight), 0) FROM mode_selection_lore"
            ).fetchone()[0]
        return {"keys": total, "total_weight": total_weight}
