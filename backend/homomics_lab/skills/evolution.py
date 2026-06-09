"""Skills evolution framework with A/B testing.

Enables comparing skill variants to drive continuous improvement.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ABTestResult:
    """Result of an A/B test comparison."""

    variant_a_wins: int
    variant_b_wins: int
    total_comparisons: int
    p_value: Optional[float]
    significant: bool
    recommendation: str


class SkillEvolution:
    """Manage skill evolution through A/B testing and variant tracking."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("./homomics_lab_evolution.db")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the evolution database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ab_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    variant_a TEXT NOT NULL,
                    variant_b TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ab_comparisons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    winner TEXT,
                    reason TEXT,
                    compared_at TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (test_id) REFERENCES ab_tests(id)
                )
            """)
            conn.commit()

    def create_test(
        self,
        test_name: str,
        skill_id: str,
        variant_a: str,
        variant_b: str,
    ) -> int:
        """Create a new A/B test. Returns test ID."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                INSERT INTO ab_tests (test_name, skill_id, variant_a, variant_b, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (test_name, skill_id, variant_a, variant_b, timestamp),
            )
            conn.commit()
            return cursor.lastrowid

    def record_comparison(
        self,
        test_id: int,
        winner: Optional[str] = None,
        reason: str = "",
        metadata: Dict[str, Any] = None,
    ) -> None:
        """Record a single comparison result."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO ab_comparisons (test_id, winner, reason, compared_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (test_id, winner, reason, timestamp, json.dumps(metadata) if metadata else None),
            )
            conn.commit()

    def get_test_results(self, test_id: int) -> Dict[str, Any]:
        """Get aggregated results for an A/B test."""
        with sqlite3.connect(str(self.db_path)) as conn:
            test = conn.execute(
                "SELECT * FROM ab_tests WHERE id = ?",
                (test_id,),
            ).fetchone()

            if not test:
                return {"error": "Test not found"}

            comparisons = conn.execute(
                """
                SELECT winner, COUNT(*) as count
                FROM ab_comparisons
                WHERE test_id = ?
                GROUP BY winner
                """,
                (test_id,),
            ).fetchall()

        wins = {row[0] or "tie": row[1] for row in comparisons}
        total = sum(wins.values())

        variant_a = test[3]
        variant_b = test[4]
        a_wins = wins.get(variant_a, 0)
        b_wins = wins.get(variant_b, 0)
        ties = wins.get("tie", 0)

        # Simple significance: require at least 10 comparisons
        significant = total >= 10 and (a_wins / total > 0.6 or b_wins / total > 0.6)

        if significant:
            if a_wins > b_wins:
                recommendation = f"Variant A ({variant_a}) is statistically better"
            else:
                recommendation = f"Variant B ({variant_b}) is statistically better"
        else:
            recommendation = "More comparisons needed for statistical significance"

        return {
            "test_id": test_id,
            "test_name": test[1],
            "skill_id": test[2],
            "variant_a": variant_a,
            "variant_b": variant_b,
            "total_comparisons": total,
            "variant_a_wins": a_wins,
            "variant_b_wins": b_wins,
            "ties": ties,
            "significant": significant,
            "recommendation": recommendation,
        }

    def list_tests(self, skill_id: str = None) -> List[Dict[str, Any]]:
        """List all A/B tests, optionally filtered by skill."""
        with sqlite3.connect(str(self.db_path)) as conn:
            if skill_id:
                rows = conn.execute(
                    "SELECT * FROM ab_tests WHERE skill_id = ? ORDER BY created_at DESC",
                    (skill_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ab_tests ORDER BY created_at DESC"
                ).fetchall()

        return [
            {
                "id": r[0],
                "test_name": r[1],
                "skill_id": r[2],
                "variant_a": r[3],
                "variant_b": r[4],
                "created_at": r[5],
                "status": r[6],
            }
            for r in rows
        ]
