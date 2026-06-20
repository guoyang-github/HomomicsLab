"""Persistent storage for WorkingMemory and TaskTree."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

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
    async def cleanup_expired(self, ttl_days: int) -> int: ...


class SQLiteSessionStore(SessionStore):
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

    async def cleanup_expired(self, ttl_days: int) -> int:
        cutoff = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM sessions WHERE updated_at < datetime(?, '-{} days')".format(ttl_days),
                (cutoff,),
            )
            await conn.commit()
            return cursor.rowcount
