"""Persistent storage for WorkingMemory and TaskTree.

Provides both a SQLite-specific implementation (legacy) and a SQLAlchemy-based
implementation that works with any database supported by SQLAlchemy (SQLite,
PostgreSQL, etc.) using the same async engine as the rest of the application.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import aiosqlite

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.tasks.task_tree import TaskTree


@dataclass
class SessionState:
    session_id: str
    project_id: str
    working_memory: WorkingMemory
    task_tree: Optional[TaskTree]
    updated_at: datetime


class SessionStore(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> Optional[SessionState]: ...

    @abstractmethod
    async def save(self, state: SessionState) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def list(self, project_id: Optional[str] = None) -> List[SessionState]: ...

    @abstractmethod
    async def cleanup_expired(self, ttl_days: int) -> int: ...


class SQLiteSessionStore(SessionStore):
    """Legacy SQLite-backed session store (kept for single-file deployments)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    working_memory TEXT NOT NULL,
                    task_tree TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            await conn.commit()

    async def get(self, session_id: str) -> Optional[SessionState]:
        async with aiosqlite.connect(self.db_path) as conn:
            row = await conn.execute(
                "SELECT project_id, working_memory, task_tree, updated_at FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await row.fetchone()
            if row is None:
                return None

        project_id, wm_json, tree_json, updated_at = row
        working_memory = WorkingMemory.from_json(wm_json)
        task_tree = TaskTree.model_validate_json(tree_json) if tree_json else None
        return SessionState(
            session_id=session_id,
            project_id=project_id,
            working_memory=working_memory,
            task_tree=task_tree,
            updated_at=datetime.fromisoformat(updated_at),
        )

    async def save(self, state: SessionState) -> None:
        wm_json = state.working_memory.to_json()
        tree_json = state.task_tree.model_dump_json() if state.task_tree else None
        updated_at = state.updated_at.isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO sessions (session_id, project_id, working_memory, task_tree, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    project_id=excluded.project_id,
                    working_memory=excluded.working_memory,
                    task_tree=excluded.task_tree,
                    updated_at=excluded.updated_at
                """,
                (state.session_id, state.project_id, wm_json, tree_json, updated_at),
            )
            await conn.commit()

    async def delete(self, session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await conn.commit()

    async def list(self, project_id: Optional[str] = None) -> List[SessionState]:
        async with aiosqlite.connect(self.db_path) as conn:
            if project_id:
                cursor = await conn.execute(
                    "SELECT session_id, project_id, working_memory, task_tree, updated_at "
                    "FROM sessions WHERE project_id = ? ORDER BY updated_at DESC",
                    (project_id,),
                )
            else:
                cursor = await conn.execute(
                    "SELECT session_id, project_id, working_memory, task_tree, updated_at "
                    "FROM sessions ORDER BY updated_at DESC"
                )
            rows = await cursor.fetchall()

        states: List[SessionState] = []
        for row in rows:
            session_id, project_id, wm_json, tree_json, updated_at = row
            states.append(
                SessionState(
                    session_id=session_id,
                    project_id=project_id,
                    working_memory=WorkingMemory.from_json(wm_json),
                    task_tree=TaskTree.model_validate_json(tree_json) if tree_json else None,
                    updated_at=datetime.fromisoformat(updated_at),
                )
            )
        return states

    async def cleanup_expired(self, ttl_days: int) -> int:
        cutoff = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM sessions WHERE updated_at < datetime(?, '-{} days')".format(ttl_days),
                (cutoff,),
            )
            await conn.commit()
            return cursor.rowcount


class SQLAlchemySessionStore(SessionStore):
    """Database-agnostic session store backed by the shared async SQLAlchemy engine.

    Works with SQLite, PostgreSQL, and any other async SQLAlchemy dialect.
    """

    def __init__(self, engine):
        self.engine = engine

    async def init(self) -> None:
        from sqlalchemy import text

        async with self.engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR PRIMARY KEY,
                    project_id VARCHAR NOT NULL,
                    working_memory TEXT NOT NULL,
                    task_tree TEXT,
                    updated_at VARCHAR NOT NULL
                )
            """))

    async def get(self, session_id: str) -> Optional[SessionState]:
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT project_id, working_memory, task_tree, updated_at "
                    "FROM sessions WHERE session_id = :session_id"
                ),
                {"session_id": session_id},
            )
            row = result.fetchone()
            if row is None:
                return None

        project_id, wm_json, tree_json, updated_at = row
        working_memory = WorkingMemory.from_json(wm_json)
        task_tree = TaskTree.model_validate_json(tree_json) if tree_json else None
        return SessionState(
            session_id=session_id,
            project_id=project_id,
            working_memory=working_memory,
            task_tree=task_tree,
            updated_at=datetime.fromisoformat(updated_at),
        )

    async def save(self, state: SessionState) -> None:
        from sqlalchemy import text

        wm_json = state.working_memory.to_json()
        tree_json = state.task_tree.model_dump_json() if state.task_tree else None
        updated_at = state.updated_at.isoformat()

        async with self.engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO sessions (session_id, project_id, working_memory, task_tree, updated_at)
                    VALUES (:session_id, :project_id, :working_memory, :task_tree, :updated_at)
                    ON CONFLICT(session_id) DO UPDATE SET
                        project_id=excluded.project_id,
                        working_memory=excluded.working_memory,
                        task_tree=excluded.task_tree,
                        updated_at=excluded.updated_at
                """),
                {
                    "session_id": state.session_id,
                    "project_id": state.project_id,
                    "working_memory": wm_json,
                    "task_tree": tree_json,
                    "updated_at": updated_at,
                },
            )

    async def delete(self, session_id: str) -> None:
        from sqlalchemy import text

        async with self.engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM sessions WHERE session_id = :session_id"),
                {"session_id": session_id},
            )

    async def list(self, project_id: Optional[str] = None) -> List[SessionState]:
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            if project_id:
                result = await conn.execute(
                    text(
                        "SELECT session_id, project_id, working_memory, task_tree, updated_at "
                        "FROM sessions WHERE project_id = :project_id ORDER BY updated_at DESC"
                    ),
                    {"project_id": project_id},
                )
            else:
                result = await conn.execute(
                    text(
                        "SELECT session_id, project_id, working_memory, task_tree, updated_at "
                        "FROM sessions ORDER BY updated_at DESC"
                    )
                )
            rows = result.fetchall()

        states: List[SessionState] = []
        for row in rows:
            session_id, project_id, wm_json, tree_json, updated_at = row
            states.append(
                SessionState(
                    session_id=session_id,
                    project_id=project_id,
                    working_memory=WorkingMemory.from_json(wm_json),
                    task_tree=TaskTree.model_validate_json(tree_json) if tree_json else None,
                    updated_at=datetime.fromisoformat(updated_at),
                )
            )
        return states

    async def cleanup_expired(self, ttl_days: int) -> int:
        from sqlalchemy import text

        cutoff = (datetime.now(timezone.utc).replace(microsecond=0)).isoformat()
        async with self.engine.begin() as conn:
            # Use a simple string comparison on ISO timestamps; lexicographic
            # ISO-8601 ordering works for UTC timestamps in both SQLite and
            # PostgreSQL.
            result = await conn.execute(
                text("DELETE FROM sessions WHERE updated_at < :cutoff"),
                {"cutoff": cutoff},
            )
            return result.rowcount


def create_session_store_from_settings():
    """Return a SessionStore appropriate for the configured session_store_url."""
    from homomics_lab.config import settings
    from homomics_lab.database.connection import get_engine

    url = settings.session_store_url
    if url.startswith("sqlite+aiosqlite:///"):
        db_path = url.replace("sqlite+aiosqlite:///", "")
        return SQLiteSessionStore(db_path=db_path)
    # For PostgreSQL and other SQLAlchemy-supported databases, reuse the engine.
    return SQLAlchemySessionStore(engine=get_engine())
