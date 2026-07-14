"""Waiting Orchestrator: event-driven suspend/resume for long-running jobs.

A running job can register a wait condition (``timer`` / ``webhook`` /
``manual``), suspend, and later be resumed when the external event arrives:

- ``timer``   — payload carries ``due_at`` (ISO-8601); a one-shot APScheduler
  job resumes the condition at due time, with ``tick()`` as a sweep fallback.
- ``webhook`` — payload carries a secret ``token`` (auto-generated when
  missing); ``resume()`` only succeeds with a matching token.
- ``manual``  — resumed explicitly through the API, no token required.

Wait conditions are persisted in a small SQLite database so they survive
process restarts; on startup ``rebuild_timer_jobs()`` re-registers pending
timer conditions with the APScheduler instance.
"""

from __future__ import annotations

import inspect
import json
import logging
import secrets
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)

CONDITION_TYPES = ("timer", "webhook", "manual")

STATUS_PENDING = "pending"
STATUS_RESUMED = "resumed"
STATUS_EXPIRED = "expired"
STATUS_CANCELLED = "cancelled"


@dataclass
class WaitCondition:
    """A registered wait condition a suspended job is blocked on."""

    wait_id: str
    job_id: str
    condition_type: str  # "timer" | "webhook" | "manual"
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = STATUS_PENDING  # pending | resumed | expired | cancelled
    created_at: str = ""
    resume_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wait_id": self.wait_id,
            "job_id": self.job_id,
            "condition_type": self.condition_type,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at,
            "resume_data": self.resume_data,
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp; naive values are treated as UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class WaitingService:
    """Register, track, and resolve wait conditions for suspended jobs.

    ``on_resume`` is an optional (sync or async) callback invoked with the
    :class:`WaitCondition` after a successful resume; ``JobService`` uses it
    to re-queue the suspended job.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        scheduler: Any = None,
        on_resume: Optional[Callable[[WaitCondition], Any]] = None,
    ):
        self.db_path = Path(db_path) if db_path else Path(settings.data_dir) / "waiting.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._scheduler = scheduler
        self._on_resume = on_resume
        self._init_db()

    @property
    def on_resume(self) -> Optional[Callable[[WaitCondition], Any]]:
        return self._on_resume

    @on_resume.setter
    def on_resume(self, fn: Optional[Callable[[WaitCondition], Any]]) -> None:
        self._on_resume = fn

    def attach_scheduler(self, scheduler: Any) -> None:
        """Attach an APScheduler instance for timer conditions."""
        self._scheduler = scheduler

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register(
        self,
        job_id: str,
        condition_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WaitCondition:
        """Register a new pending wait condition for a job."""
        if condition_type not in CONDITION_TYPES:
            raise ValueError(
                f"Unknown condition_type {condition_type!r}; expected one of {CONDITION_TYPES}"
            )
        payload = dict(payload or {})
        if condition_type == "webhook" and not payload.get("token"):
            payload["token"] = secrets.token_urlsafe(16)
        now = _utcnow_iso()
        condition = WaitCondition(
            wait_id=f"wait_{uuid.uuid4().hex[:12]}",
            job_id=job_id,
            condition_type=condition_type,
            payload=payload,
            status=STATUS_PENDING,
            created_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO wait_conditions"
                " (wait_id, job_id, condition_type, payload, status, resume_data, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    condition.wait_id,
                    condition.job_id,
                    condition.condition_type,
                    json.dumps(condition.payload),
                    condition.status,
                    None,
                    now,
                    now,
                ),
            )
        if condition_type == "timer":
            self._schedule_timer(condition)
        return condition

    def get(self, wait_id: str) -> Optional[WaitCondition]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT wait_id, job_id, condition_type, payload, status, resume_data, created_at"
                " FROM wait_conditions WHERE wait_id = ?",
                (wait_id,),
            ).fetchone()
        return self._row_to_condition(row) if row else None

    def list_pending(self, job_id: Optional[str] = None) -> List[WaitCondition]:
        query = (
            "SELECT wait_id, job_id, condition_type, payload, status, resume_data, created_at"
            " FROM wait_conditions WHERE status = ?"
        )
        params: tuple = (STATUS_PENDING,)
        if job_id is not None:
            query += " AND job_id = ?"
            params = (STATUS_PENDING, job_id)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_condition(row) for row in rows]

    async def resume(
        self,
        wait_id: str,
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> bool:
        """Resolve a pending wait condition.

        ``webhook`` conditions require the token issued at registration time.
        Returns True when the condition transitioned to ``resumed``.
        """
        condition = self.get(wait_id)
        if condition is None or condition.status != STATUS_PENDING:
            return False
        if condition.condition_type == "webhook":
            expected = str(condition.payload.get("token") or "")
            if not expected or not token or not secrets.compare_digest(expected, str(token)):
                return False
        now = _utcnow_iso()
        resume_json = json.dumps(data) if data is not None else None
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE wait_conditions SET status = ?, resume_data = ?, updated_at = ?"
                " WHERE wait_id = ? AND status = ?",
                (STATUS_RESUMED, resume_json, now, wait_id, STATUS_PENDING),
            )
        if cursor.rowcount == 0:
            return False
        self._unschedule_timer(wait_id)
        condition.status = STATUS_RESUMED
        condition.resume_data = data
        if self._on_resume is not None:
            try:
                result = self._on_resume(condition)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("on_resume callback failed for wait %s", wait_id)
        return True

    def cancel(self, wait_id: str) -> bool:
        """Cancel a pending wait condition. Returns True when transitioned."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE wait_conditions SET status = ?, updated_at = ?"
                " WHERE wait_id = ? AND status = ?",
                (STATUS_CANCELLED, _utcnow_iso(), wait_id, STATUS_PENDING),
            )
        if cursor.rowcount > 0:
            self._unschedule_timer(wait_id)
            return True
        return False

    def expire_old(self, now: Optional[datetime] = None) -> int:
        """Expire pending conditions whose ``payload.expires_at`` has passed."""
        now = now or _utcnow()
        expired = 0
        for condition in self.list_pending():
            expires_at = _parse_iso(condition.payload.get("expires_at"))
            if expires_at is None or expires_at > now:
                continue
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE wait_conditions SET status = ?, updated_at = ?"
                    " WHERE wait_id = ? AND status = ?",
                    (STATUS_EXPIRED, _utcnow_iso(), condition.wait_id, STATUS_PENDING),
                )
            if cursor.rowcount > 0:
                self._unschedule_timer(condition.wait_id)
                expired += 1
        return expired

    # ------------------------------------------------------------------
    # Timer support
    # ------------------------------------------------------------------

    async def tick(self, now: Optional[datetime] = None) -> int:
        """Resume all timer conditions whose ``due_at`` has passed.

        Fallback sweep meant to be called periodically by an external
        scheduler so missed one-shot jobs (e.g. after a restart) still fire.
        """
        now = now or _utcnow()
        fired = 0
        for condition in self.list_pending():
            if condition.condition_type != "timer":
                continue
            due_at = _parse_iso(condition.payload.get("due_at"))
            if due_at is not None and due_at <= now:
                if await self.resume(condition.wait_id):
                    fired += 1
        return fired

    def rebuild_timer_jobs(self) -> int:
        """Re-register one-shot scheduler jobs for pending timer conditions.

        Called on startup after attaching the scheduler so timers persisted
        before a restart are honored. Already-overdue conditions fire
        immediately.
        """
        if self._scheduler is None:
            return 0
        count = 0
        for condition in self.list_pending():
            if condition.condition_type == "timer":
                self._schedule_timer(condition)
                count += 1
        return count

    def _schedule_timer(self, condition: WaitCondition) -> None:
        if self._scheduler is None:
            return
        due_at = _parse_iso(condition.payload.get("due_at"))
        if due_at is None:
            logger.warning(
                "Timer wait %s has no valid due_at; relying on tick()", condition.wait_id
            )
            return
        from apscheduler.triggers.date import DateTrigger

        # run_date=None fires immediately, covering already-overdue timers.
        trigger = DateTrigger(run_date=due_at if due_at > _utcnow() else None)

        async def _fire() -> None:
            await self.resume(condition.wait_id)

        try:
            self._scheduler.add_job(
                _fire,
                trigger=trigger,
                id=f"wait_timer_{condition.wait_id}",
                name=f"wait_timer_{condition.wait_id}",
                replace_existing=True,
                max_instances=1,
            )
        except Exception:
            logger.warning(
                "Failed to schedule timer wait %s", condition.wait_id, exc_info=True
            )

    def _unschedule_timer(self, wait_id: str) -> None:
        if self._scheduler is None:
            return
        try:
            self._scheduler.remove_job(f"wait_timer_{wait_id}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS wait_conditions (
                    wait_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    condition_type TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending',
                    resume_data TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_wc_job_id ON wait_conditions(job_id);
                CREATE INDEX IF NOT EXISTS idx_wc_status ON wait_conditions(status);
                """
            )

    @staticmethod
    def _row_to_condition(row: tuple) -> WaitCondition:
        wait_id, job_id, condition_type, payload, status, resume_data, created_at = row
        return WaitCondition(
            wait_id=wait_id,
            job_id=job_id,
            condition_type=condition_type,
            payload=json.loads(payload) if payload else {},
            status=status,
            created_at=created_at,
            resume_data=json.loads(resume_data) if resume_data else None,
        )
