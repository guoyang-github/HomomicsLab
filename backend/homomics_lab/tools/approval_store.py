"""Persistent storage for tool approval requests.

Keeps approvals durable across process restarts and supports multi-node
setups. Falls back to in-memory if the database is unavailable.
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolApprovalRequest:
    """Pending or resolved approval for a high-risk tool call."""

    call_id: str
    tool_name: str
    arguments: Dict
    risk_level: str
    approved: bool = False
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "risk_level": self.risk_level,
            "approved": self.approved,
            "metadata": self.metadata,
        }


class PersistentApprovalStore:
    """SQLite-backed approval store with in-memory fallback."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.data_dir / ".metadata" / "approvals.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory: Dict[str, ToolApprovalRequest] = {}
        self._available = self._init_db()

    def _init_db(self) -> bool:
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS approvals (
                        call_id TEXT PRIMARY KEY,
                        tool_name TEXT NOT NULL,
                        arguments TEXT NOT NULL,
                        risk_level TEXT NOT NULL,
                        approved INTEGER NOT NULL DEFAULT 0,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        resolved_at TEXT,
                        resolver TEXT,
                        reason TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_approvals_pending ON approvals(approved)"
                )
            return True
        except Exception as exc:
            logger.warning("Approval database unavailable, using memory fallback: %s", exc)
            return False

    def create_request(
        self,
        tool_name: str,
        arguments: Dict,
        risk_level: str,
    ) -> ToolApprovalRequest:
        call_id = str(uuid.uuid4())
        request = ToolApprovalRequest(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
        )
        if self._available:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    conn.execute(
                        """
                        INSERT INTO approvals (call_id, tool_name, arguments, risk_level, approved, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            call_id,
                            tool_name,
                            json.dumps(arguments, ensure_ascii=False, default=str),
                            risk_level,
                            0,
                            json.dumps(request.metadata, ensure_ascii=False),
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
            except Exception as exc:
                logger.warning("Failed to persist approval request: %s", exc)
        self._memory[call_id] = request
        return request

    def get(self, call_id: str) -> Optional[ToolApprovalRequest]:
        if call_id in self._memory:
            return self._memory[call_id]
        if not self._available:
            return None
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                row = conn.execute(
                    "SELECT tool_name, arguments, risk_level, approved, metadata FROM approvals WHERE call_id = ?",
                    (call_id,),
                ).fetchone()
            if row is None:
                return None
            request = ToolApprovalRequest(
                call_id=call_id,
                tool_name=row[0],
                arguments=json.loads(row[1]),
                risk_level=row[2],
                approved=bool(row[3]),
                metadata=json.loads(row[4] or "{}"),
            )
            self._memory[call_id] = request
            return request
        except Exception as exc:
            logger.warning("Failed to load approval request: %s", exc)
            return None

    def approve(
        self,
        call_id: str,
        resolver: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        return self._resolve(call_id, approved=True, resolver=resolver, reason=reason)

    def reject(
        self,
        call_id: str,
        resolver: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        return self._resolve(call_id, approved=False, resolver=resolver, reason=reason)

    def _resolve(
        self,
        call_id: str,
        approved: bool,
        resolver: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        request = self.get(call_id)
        if request is None:
            return False
        request.approved = approved
        if self._available:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    conn.execute(
                        """
                        UPDATE approvals
                        SET approved = ?, resolved_at = ?, resolver = ?, reason = ?
                        WHERE call_id = ?
                        """,
                        (
                            1 if approved else 0,
                            datetime.now(timezone.utc).isoformat(),
                            resolver,
                            reason,
                            call_id,
                        ),
                    )
            except Exception as exc:
                logger.warning("Failed to update approval request: %s", exc)
        return True

    def is_approved(self, call_id: str) -> bool:
        request = self.get(call_id)
        return request is not None and request.approved

    def list_pending(self) -> List[ToolApprovalRequest]:
        if not self._available:
            return [r for r in self._memory.values() if not r.approved]
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                rows = conn.execute(
                    "SELECT call_id, tool_name, arguments, risk_level, approved, metadata FROM approvals WHERE approved = 0"
                ).fetchall()
            return [
                ToolApprovalRequest(
                    call_id=row[0],
                    tool_name=row[1],
                    arguments=json.loads(row[2]),
                    risk_level=row[3],
                    approved=bool(row[4]),
                    metadata=json.loads(row[5] or "{}"),
                )
                for row in rows
            ]
        except Exception as exc:
            logger.warning("Failed to list pending approvals: %s", exc)
            return []
