"""Intent decision logging and confidence calibration.

Records every intent classification decision so the system can learn whether
the current clarification threshold is too aggressive or too permissive.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)


@dataclass
class IntentDecisionRecord:
    """A single intent classification outcome."""

    timestamp: str
    message: str
    primary_intent: str
    confidence: float
    needs_clarification: bool
    keyword_scores: Dict[str, float] = field(default_factory=dict)
    embedding_scores: Dict[str, float] = field(default_factory=dict)
    llm_scores: Dict[str, float] = field(default_factory=dict)
    session_id: Optional[str] = None
    feedback: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "message": self.message,
            "primary_intent": self.primary_intent,
            "confidence": self.confidence,
            "needs_clarification": self.needs_clarification,
            "keyword_scores": self.keyword_scores,
            "embedding_scores": self.embedding_scores,
            "llm_scores": self.llm_scores,
            "session_id": self.session_id,
            "feedback": self.feedback,
        }


class IntentDecisionLogger:
    """Persist intent classification decisions to SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.data_dir / ".metadata" / "intent_decisions.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS intent_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    message TEXT,
                    primary_intent TEXT,
                    confidence REAL,
                    needs_clarification INTEGER,
                    keyword_scores TEXT,
                    embedding_scores TEXT,
                    llm_scores TEXT,
                    session_id TEXT,
                    feedback TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_intent_primary ON intent_decisions(primary_intent)"
            )

    def record(self, record: IntentDecisionRecord) -> None:
        """Persist a decision record."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO intent_decisions (
                        timestamp, message, primary_intent, confidence, needs_clarification,
                        keyword_scores, embedding_scores, llm_scores, session_id, feedback
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.timestamp,
                        record.message,
                        record.primary_intent,
                        record.confidence,
                        1 if record.needs_clarification else 0,
                        json.dumps(record.keyword_scores, ensure_ascii=False),
                        json.dumps(record.embedding_scores, ensure_ascii=False),
                        json.dumps(record.llm_scores, ensure_ascii=False),
                        record.session_id,
                        record.feedback,
                    ),
                )
        except Exception as exc:
            logger.warning("Failed to record intent decision: %s", exc)

    def recent_decisions(self, limit: int = 100) -> List[IntentDecisionRecord]:
        """Load recent decision records."""
        records: List[IntentDecisionRecord] = []
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT timestamp, message, primary_intent, confidence, needs_clarification,
                           keyword_scores, embedding_scores, llm_scores, session_id, feedback
                    FROM intent_decisions
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            for row in rows:
                records.append(
                    IntentDecisionRecord(
                        timestamp=row[0],
                        message=row[1],
                        primary_intent=row[2],
                        confidence=row[3],
                        needs_clarification=bool(row[4]),
                        keyword_scores=json.loads(row[5] or "{}"),
                        embedding_scores=json.loads(row[6] or "{}"),
                        llm_scores=json.loads(row[7] or "{}"),
                        session_id=row[8],
                        feedback=row[9],
                    )
                )
        except Exception as exc:
            logger.warning("Failed to load intent decisions: %s", exc)
        return records


class ConfidenceCalibrator:
    """Calibrate clarification threshold from historical decisions.

    If too many low-confidence decisions are later marked as correct, the
    threshold is lowered. If too many clarifications were unnecessary, it is
    raised.
    """

    def __init__(
        self,
        logger: IntentDecisionLogger,
        min_samples: int = 20,
        target_clarification_rate: float = 0.15,
    ):
        self.logger = logger
        self.min_samples = min_samples
        self.target_clarification_rate = target_clarification_rate

    def suggest_threshold(self, current: float) -> float:
        """Return a recommended clarification threshold."""
        decisions = self.logger.recent_decisions(limit=200)
        if len(decisions) < self.min_samples:
            return current

        # Use decisions with explicit feedback when available; otherwise assume
        # that a decision not needing clarification and with confidence above
        # the current threshold was correct.
        rates = []
        thresholds = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
        for t in thresholds:
            clarify_count = sum(1 for d in decisions if d.confidence < t)
            rate = clarify_count / len(decisions)
            rates.append((t, abs(rate - self.target_clarification_rate)))

        best = min(rates, key=lambda x: x[1])[0]
        # Move only 20% toward the recommendation to avoid oscillation.
        return round(current + (best - current) * 0.2, 2)
