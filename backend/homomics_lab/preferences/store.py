"""Persistent store for user preferences learned from HITL and explicit feedback."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class UserPreferenceStore:
    """SQLite-backed store for user preferences.

    Preferences are scoped by ``project_id`` and can target a skill, phase,
    parameter, or generic checkpoint.  Each entry stores the preferred value,
    an importance score, and timestamps for staleness-based eviction.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or str(Path("data") / "preferences.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                scope_type TEXT NOT NULL,
                scope_id TEXT,
                key TEXT,
                value TEXT NOT NULL,
                preference_type TEXT NOT NULL DEFAULT 'default',
                importance REAL NOT NULL DEFAULT 0.5,
                context_hash TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_prefs_project_scope
            ON user_preferences(project_id, scope_type, scope_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_prefs_context_hash
            ON user_preferences(context_hash)
        """)
        conn.commit()

    def record(
        self,
        project_id: str,
        scope_type: str,
        scope_id: Optional[str],
        key: Optional[str],
        value: Any,
        preference_type: str = "default",
        importance: float = 0.5,
        context_hash: Optional[str] = None,
    ) -> int:
        """Record or update a preference.

        Returns:
            The preference row id.
        """
        now = datetime.now(timezone.utc).isoformat()
        value_json = json.dumps(value, ensure_ascii=False)
        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO user_preferences (
                project_id, scope_type, scope_id, key, value, preference_type,
                importance, context_hash, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                value = excluded.value,
                preference_type = excluded.preference_type,
                importance = excluded.importance,
                context_hash = excluded.context_hash,
                updated_at = excluded.updated_at
            """,
            (
                project_id,
                scope_type,
                scope_id,
                key,
                value_json,
                preference_type,
                importance,
                context_hash,
                now,
                now,
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def get(
        self,
        project_id: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve matching preferences ordered by importance desc, recency desc."""
        conn = self._get_conn()
        filters = ["project_id = ?"]
        params: List[Any] = [project_id]
        if scope_type is not None:
            filters.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            filters.append("scope_id = ?")
            params.append(scope_id)
        if key is not None:
            filters.append("key = ?")
            params.append(key)
        where = "WHERE " + " AND ".join(filters)
        rows = conn.execute(
            f"""
            SELECT * FROM user_preferences
            {where}
            ORDER BY importance DESC, updated_at DESC
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_default(
        self,
        project_id: str,
        scope_type: str,
        scope_id: Optional[str],
        key: Optional[str] = None,
    ) -> Optional[Any]:
        """Return the single most relevant default preference value, if any."""
        prefs = self.get(project_id, scope_type=scope_type, scope_id=scope_id, key=key)
        if not prefs:
            return None
        try:
            return json.loads(prefs[0]["value"])
        except Exception:
            return prefs[0]["value"]

    def delete(
        self,
        project_id: str,
        scope_type: str,
        scope_id: Optional[str] = None,
        key: Optional[str] = None,
    ) -> int:
        """Delete matching preferences. Returns number of rows deleted."""
        conn = self._get_conn()
        filters = ["project_id = ?", "scope_type = ?"]
        params: List[Any] = [project_id, scope_type]
        if scope_id is not None:
            filters.append("scope_id = ?")
            params.append(scope_id)
        if key is not None:
            filters.append("key = ?")
            params.append(key)
        where = "WHERE " + " AND ".join(filters)
        cursor = conn.execute(f"DELETE FROM user_preferences {where}", params)
        conn.commit()
        return cursor.rowcount

    def prune_stale(self, retention_days: int = 90) -> int:
        """Remove preferences that have not been updated recently."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM user_preferences WHERE date(updated_at) <= date('now', '-' || ? || ' days')",
            (retention_days,),
        )
        conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
