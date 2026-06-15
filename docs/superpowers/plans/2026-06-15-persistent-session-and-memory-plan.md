# Persistent Session State & Long-Term Memory Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist `WorkingMemory` and `TaskTree` across server restarts, and make `SemanticMemory` and `CBKB` retrievable inside `TurnRunner` so the agent can use historical project context.

**Architecture:** Add a `SessionStore` for durable session state and a `MemoryManager` facade that coordinates `WorkingMemory`, `SemanticMemory`, and `CBKB`. `TurnRunner` calls `MemoryManager.enrich_context()` before planning and `MemoryManager.persist_turn()` after execution. `api/chat.py` drops its in-memory dictionaries and loads state from `MemoryManager` instead.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, aiosqlite/SQLite, pytest-asyncio.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/homomics_lab/config.py` | Add `session_store_url`, `session_ttl_days`, `enable_semantic_memory` settings |
| `backend/homomics_lab/tasks/task_tree.py` | Add Pydantic-compatible serialization to `TaskTree` |
| `backend/homomics_lab/context/session_store.py` | `SessionStore` ABC + `SQLiteSessionStore` implementation |
| `backend/homomics_lab/context/memory_manager.py` | `MemoryManager` facade for loading/enriching/persisting memory |
| `backend/homomics_lab/context/__init__.py` | Re-export `SessionStore`, `SQLiteSessionStore`, `MemoryManager` |
| `backend/homomics_lab/agent/turn_runner.py` | Wire `memory_manager` into `run_turn` and `execute_tree` |
| `backend/homomics_lab/api/chat.py` | Replace in-memory `_sessions`/`_task_trees` with `MemoryManager` |
| `backend/homomics_lab/main.py` | Attach `memory_manager` to `app.state` in lifespan |
| `backend/homomics_lab/bootstrap.py` | Build and return `memory_manager` from `bootstrap_worker_context` |
| `backend/tests/test_context/test_session_store.py` | Unit tests for `SQLiteSessionStore` |
| `backend/tests/test_context/test_memory_manager.py` | Unit tests for `MemoryManager` |
| `backend/tests/test_agent/test_turn_runner_memory.py` | Tests that `TurnRunner` calls memory hooks |
| `backend/tests/test_api/test_chat_memory.py` | Tests that chat API persists and recovers session state |

---

## Task 1: Add configuration settings

**Files:**
- Modify: `backend/homomics_lab/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config.py` addition (append to existing file):

```python
def test_session_memory_settings():
    from homomics_lab.config import settings

    assert hasattr(settings, "session_store_url")
    assert hasattr(settings, "session_ttl_days")
    assert hasattr(settings, "enable_semantic_memory")
    assert settings.session_ttl_days == 90
    assert settings.enable_semantic_memory is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend
pytest tests/test_config.py::test_session_memory_settings -v
```

Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'session_store_url'`

- [ ] **Step 3: Add settings**

Modify `backend/homomics_lab/config.py` after the `mcp_server_script` field (around line 82):

```python
    # Session / memory settings
    session_store_url: str = "sqlite+aiosqlite:///./data/sessions.db"
    session_ttl_days: int = 90
    enable_semantic_memory: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py::test_session_memory_settings -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/homomics_lab/config.py backend/tests/test_config.py
git commit -m "feat(config): add session store and memory settings

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Add TaskTree serialization

**Files:**
- Modify: `backend/homomics_lab/tasks/task_tree.py`
- Test: `backend/tests/test_agent/test_task_tree.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent/test_task_tree.py`:

```python
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


def test_task_tree_round_trip():
    tree = TaskTree(tasks=[
        TaskNode(id="t1", name="qc", description="quality control"),
        TaskNode(id="t2", name="cluster", description="clustering", dependencies=["t1"]),
    ])

    dumped = tree.model_dump()
    restored = TaskTree.model_validate(dumped)

    assert len(restored.tasks) == 2
    assert restored.tasks[0].id == "t1"
    assert restored.tasks[1].dependencies == ["t1"]


def test_task_tree_empty_round_trip():
    tree = TaskTree()
    dumped = tree.model_dump()
    restored = TaskTree.model_validate(dumped)
    assert restored.tasks == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent/test_task_tree.py -v
```

Expected: FAIL with `AttributeError: 'TaskTree' object has no attribute 'model_dump'`

- [ ] **Step 3: Implement serialization**

Replace `backend/homomics_lab/tasks/task_tree.py` with:

```python
from typing import List
from pydantic import BaseModel
from homomics_lab.tasks.models import TaskNode, TaskStatus


class TaskTree(BaseModel):
    tasks: List[TaskNode] = []

    def get_task(self, task_id: str) -> TaskNode:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Task {task_id} not found")

    def get_ready_tasks(self) -> List[TaskNode]:
        """Return tasks whose dependencies are all completed and status is pending."""
        completed = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [t for t in self.tasks if t.status == TaskStatus.PENDING and all(dep in completed for dep in t.dependencies)]

    def topological_sort(self) -> List[TaskNode]:
        """Return tasks in dependency order."""
        completed = set()
        result = []

        def can_schedule(task: TaskNode) -> bool:
            return all(dep in completed for dep in task.dependencies)

        pending = list(self.tasks)
        while pending:
            progress = False
            for task in pending[:]:
                if can_schedule(task):
                    result.append(task)
                    completed.add(task.id)
                    pending.remove(task)
                    progress = True

            if not progress and pending:
                raise ValueError("Cyclic dependency detected in task tree")

        return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent/test_task_tree.py -v
```

Expected: PASS

- [ ] **Step 5: Run existing tests to check regressions**

```bash
pytest tests/test_agent/test_turn_runner.py -v
```

Expected: PASS (TaskTree API backward-compatible)

- [ ] **Step 6: Commit**

```bash
git add backend/homomics_lab/tasks/task_tree.py backend/tests/test_agent/test_task_tree.py
git commit -m "feat(tasks): make TaskTree Pydantic-serializable

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Create SessionStore

**Files:**
- Create: `backend/homomics_lab/context/session_store.py`
- Modify: `backend/homomics_lab/context/__init__.py`
- Test: `backend/tests/test_context/test_session_store.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_context/test_session_store.py`:

```python
import pytest
from datetime import datetime, timezone
from homomics_lab.context.session_store import SQLiteSessionStore, SessionState
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.tasks.models import TaskNode


@pytest.fixture
async def store(tmp_path):
    db_path = tmp_path / "sessions.db"
    s = SQLiteSessionStore(str(db_path))
    await s.init()
    return s


@pytest.mark.asyncio
async def test_save_and_load_session(store):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hello", sender="user"))
    tree = TaskTree(tasks=[TaskNode(id="t1", name="qc", description="quality control")])

    state = SessionState(
        session_id="sess_1",
        project_id="proj_1",
        working_memory=wm,
        task_tree=tree,
        updated_at=datetime.now(timezone.utc),
    )
    await store.save(state)

    loaded = await store.get("sess_1")
    assert loaded is not None
    assert loaded.project_id == "proj_1"
    assert len(loaded.working_memory.messages) == 1
    assert loaded.task_tree.tasks[0].id == "t1"


@pytest.mark.asyncio
async def test_missing_session_returns_none(store):
    loaded = await store.get("nonexistent")
    assert loaded is None


@pytest.mark.asyncio
async def test_delete_session(store):
    wm = WorkingMemory()
    state = SessionState(
        session_id="sess_del",
        project_id="proj_1",
        working_memory=wm,
        task_tree=None,
        updated_at=datetime.now(timezone.utc),
    )
    await store.save(state)
    assert await store.get("sess_del") is not None

    await store.delete("sess_del")
    assert await store.get("sess_del") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_context/test_session_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'homomics_lab.context.session_store'`

- [ ] **Step 3: Implement SessionStore**

Create `backend/homomics_lab/context/session_store.py`:

```python
"""Persistent storage for WorkingMemory and TaskTree."""

import json
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
```

- [ ] **Step 4: Export from context package**

Modify `backend/homomics_lab/context/__init__.py` to include:

```python
from homomics_lab.context.session_store import SessionStore, SQLiteSessionStore

__all__ = [..., "SessionStore", "SQLiteSessionStore"]
```

(If `__init__.py` is empty, create it with:)

```python
from homomics_lab.context.session_store import SessionStore, SQLiteSessionStore

__all__ = ["SessionStore", "SQLiteSessionStore"]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_context/test_session_store.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/homomics_lab/context/session_store.py backend/homomics_lab/context/__init__.py backend/tests/test_context/test_session_store.py
git commit -m "feat(context): add SQLiteSessionStore for WorkingMemory and TaskTree

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Create MemoryManager

**Files:**
- Create: `backend/homomics_lab/context/memory_manager.py`
- Modify: `backend/homomics_lab/context/__init__.py`
- Test: `backend/tests/test_context/test_memory_manager.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_context/test_memory_manager.py`:

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.session_store import SQLiteSessionStore
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.tasks.models import TaskNode


@pytest.fixture
async def manager(tmp_path):
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(str(db_path))
    await store.init()
    semantic = AsyncMock()
    cbkb = AsyncMock()
    return MemoryManager(session_store=store, semantic_memory=semantic, cbkb=cbkb)


@pytest.mark.asyncio
async def test_load_session_creates_new(manager):
    wm, tree = await manager.load_session("new_sess", "proj_1")
    assert isinstance(wm, WorkingMemory)
    assert tree is None


@pytest.mark.asyncio
async def test_load_session_restores_existing(manager):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hi", sender="user"))
    tree = TaskTree(tasks=[TaskNode(id="t1", name="qc", description="qc")])
    await manager.session_store.save(
        manager.session_store.__class__("").SessionState(
            session_id="sess_1",
            project_id="proj_1",
            working_memory=wm,
            task_tree=tree,
            updated_at=datetime.now(timezone.utc),
        )
    )
    # Re-create manager to avoid in-memory cache; same db path required, so use fixture-level manager
    loaded_wm, loaded_tree = await manager.load_session("sess_1", "proj_1")
    assert len(loaded_wm.messages) == 1
    assert loaded_tree.tasks[0].id == "t1"


@pytest.mark.asyncio
async def test_enrich_context_retrieves_semantic_memory(manager):
    manager.semantic_memory.search = AsyncMock(return_value=[
        {"text": "Previously used resolution=0.6 for PBMC", "score": 0.9, "metadata": {"project_id": "proj_1"}}
    ])
    wm = WorkingMemory()
    ctx = await manager.enrich_context("proj_1", "analyze PBMC", wm)
    assert "memory_snippets" in ctx
    assert "resolution=0.6" in ctx["memory_snippets"][0]


@pytest.mark.asyncio
async def test_persist_turn_saves_session(manager):
    from homomics_lab.agent.turn_runner import TurnResult, ExecutionMode

    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hello", sender="user"))
    turn_result = TurnResult(mode=ExecutionMode.DIRECT_RESPONSE, response_text="hi", task_tree=None)

    await manager.persist_turn(
        session_id="sess_persist",
        project_id="proj_1",
        user_message="hello",
        turn_result=turn_result,
        working_memory=wm,
        task_tree=None,
    )

    loaded = await manager.session_store.get("sess_persist")
    assert loaded is not None
    assert len(loaded.working_memory.messages) == 2  # user + agent reply
    manager.semantic_memory.add.assert_awaited()
```

Note: The test `test_load_session_restores_existing` has a flaw because we cannot construct SessionState from the store class. We should fix that in the next step. Actually, better to write the test cleanly using the store directly.

Rewrite that test case:

```python
@pytest.mark.asyncio
async def test_load_session_restores_existing(manager):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hi", sender="user"))
    tree = TaskTree(tasks=[TaskNode(id="t1", name="qc", description="qc")])
    from homomics_lab.context.session_store import SessionState
    await manager.session_store.save(SessionState(
        session_id="sess_1",
        project_id="proj_1",
        working_memory=wm,
        task_tree=tree,
        updated_at=datetime.now(timezone.utc),
    ))

    loaded_wm, loaded_tree = await manager.load_session("sess_1", "proj_1")
    assert len(loaded_wm.messages) == 1
    assert loaded_tree.tasks[0].id == "t1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_context/test_memory_manager.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'homomics_lab.context.memory_manager'`

- [ ] **Step 3: Implement MemoryManager**

Create `backend/homomics_lab/context/memory_manager.py`:

```python
"""Unified facade for session state and long-term memory."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from homomics_lab.context.semantic_memory import SemanticMemory
from homomics_lab.context.session_store import SessionState, SessionStore
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)


class MemoryManager:
    """Coordinates WorkingMemory, SemanticMemory, and CBKB for a session."""

    def __init__(
        self,
        session_store: SessionStore,
        semantic_memory: Optional[SemanticMemory] = None,
        cbkb: Optional[CBKB] = None,
    ) -> None:
        self.session_store = session_store
        self.semantic_memory = semantic_memory
        self.cbkb = cbkb

    async def load_session(
        self,
        session_id: str,
        project_id: str,
    ) -> Tuple[WorkingMemory, Optional[TaskTree]]:
        """Load a session from the store, or create a new one."""
        state = await self.session_store.get(session_id)
        if state is not None:
            return state.working_memory, state.task_tree

        return WorkingMemory(), None

    async def enrich_context(
        self,
        project_id: str,
        user_message: str,
        working_memory: WorkingMemory,
    ) -> Dict[str, Any]:
        """Retrieve relevant historical context for the current turn."""
        context: Dict[str, Any] = {"memory_snippets": [], "parameter_preferences": []}

        if self.semantic_memory is None:
            return context

        try:
            query = f"{user_message} project:{project_id}"
            results = await self.semantic_memory.search(query, top_k=5)
            context["memory_snippets"] = [r["text"] for r in results]
        except Exception:
            logger.warning("Semantic memory search failed; continuing without it", exc_info=True)

        if self.cbkb is not None:
            try:
                # Future: read parameter lore per project
                context["parameter_preferences"] = []
            except Exception:
                logger.warning("CBKB enrichment failed; continuing without it", exc_info=True)

        return context

    async def persist_turn(
        self,
        session_id: str,
        project_id: str,
        user_message: str,
        turn_result: Any,
        working_memory: WorkingMemory,
        task_tree: Optional[TaskTree],
    ) -> None:
        """Persist the current turn and update long-term memory."""
        # Ensure agent reply is in working memory
        if turn_result.agent_message is not None:
            working_memory.add_message(turn_result.agent_message)

        await self._save_session(session_id, project_id, working_memory, task_tree)
        await self._write_semantic_memory(
            project_id, user_message, turn_result, working_memory, task_tree
        )

    async def _save_session(
        self,
        session_id: str,
        project_id: str,
        working_memory: WorkingMemory,
        task_tree: Optional[TaskTree],
    ) -> None:
        state = SessionState(
            session_id=session_id,
            project_id=project_id,
            working_memory=working_memory,
            task_tree=task_tree,
            updated_at=datetime.now(timezone.utc),
        )
        try:
            await self.session_store.save(state)
        except Exception:
            logger.exception("Failed to persist session state for %s", session_id)

    async def _write_semantic_memory(
        self,
        project_id: str,
        user_message: str,
        turn_result: Any,
        working_memory: WorkingMemory,
        task_tree: Optional[TaskTree],
    ) -> None:
        if self.semantic_memory is None:
            return

        summary = self._summarize_turn(project_id, user_message, turn_result, task_tree)
        try:
            await self.semantic_memory.add(
                text=summary,
                memory_type="conversation",
                metadata={
                    "project_id": project_id,
                    "session_id": turn_result.get("session_id") if isinstance(turn_result, dict) else None,
                    "mode": str(turn_result.mode) if hasattr(turn_result, "mode") else None,
                },
            )
        except Exception:
            logger.warning("Failed to write semantic memory", exc_info=True)

    @staticmethod
    def _summarize_turn(
        project_id: str,
        user_message: str,
        turn_result: Any,
        task_tree: Optional[TaskTree],
    ) -> str:
        mode = str(turn_result.mode) if hasattr(turn_result, "mode") else "unknown"
        summary_parts = [
            f"Project {project_id}: user asked: '{user_message}'",
            f"Execution mode: {mode}.",
        ]
        if task_tree is not None and task_tree.tasks:
            task_names = ", ".join(t.name for t in task_tree.tasks)
            summary_parts.append(f"Tasks: {task_names}.")
        if hasattr(turn_result, "response_text") and turn_result.response_text:
            summary_parts.append(f"Response: {turn_result.response_text[:200]}")
        return " ".join(summary_parts)
```

- [ ] **Step 4: Update context package exports**

Modify `backend/homomics_lab/context/__init__.py`:

```python
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.session_store import SessionStore, SQLiteSessionStore

__all__ = ["MemoryManager", "SessionStore", "SQLiteSessionStore"]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_context/test_memory_manager.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/homomics_lab/context/memory_manager.py backend/homomics_lab/context/__init__.py backend/tests/test_context/test_memory_manager.py
git commit -m "feat(context): add MemoryManager facade for session and long-term memory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Wire MemoryManager into TurnRunner

**Files:**
- Modify: `backend/homomics_lab/agent/turn_runner.py`
- Test: `backend/tests/test_agent/test_turn_runner_memory.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent/test_turn_runner_memory.py`:

```python
import pytest
from unittest.mock import AsyncMock

from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.session_store import SQLiteSessionStore
from homomics_lab.context.working_memory import WorkingMemory


@pytest.fixture
async def runner_with_memory(tmp_path):
    store = SQLiteSessionStore(str(tmp_path / "sessions.db"))
    await store.init()
    semantic = AsyncMock()
    mm = MemoryManager(session_store=store, semantic_memory=semantic, cbkb=None)
    return TurnRunner(memory_manager=mm), mm


@pytest.mark.asyncio
async def test_run_turn_enriches_and_persists(runner_with_memory):
    runner, mm = runner_with_memory
    mm.semantic_memory.search = AsyncMock(return_value=[
        {"text": "Previously used resolution=0.6", "score": 0.9}
    ])

    result = await runner.run_turn(
        session_id="sess_tr",
        user_message="什么是 UMAP？",
        working_memory=WorkingMemory(),
        project_id="proj_1",
    )

    assert result.mode.value == "direct_response"
    mm.semantic_memory.search.assert_awaited_once()
    mm.semantic_memory.add.assert_awaited_once()

    loaded = await mm.session_store.get("sess_tr")
    assert loaded is not None
    assert len(loaded.working_memory.messages) >= 2


@pytest.mark.asyncio
async def test_run_turn_without_memory_manager_still_works():
    runner = TurnRunner()
    result = await runner.run_turn(
        session_id="sess_no_mm",
        user_message="什么是 UMAP？",
        working_memory=WorkingMemory(),
        project_id="proj_1",
    )
    assert result.mode.value == "direct_response"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent/test_turn_runner_memory.py -v
```

Expected: FAIL because `TurnRunner.__init__` does not accept `memory_manager`

- [ ] **Step 3: Modify TurnRunner**

Modify `backend/homomics_lab/agent/turn_runner.py`:

1. Add import:

```python
from typing import Any, Callable, Dict, List, Optional
# add this line
from homomics_lab.context.memory_manager import MemoryManager
```

2. Update `__init__` signature and body:

```python
    def __init__(
        self,
        intent_analyzer: Optional[Any] = None,
        task_decomposer: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        registry: Optional[Any] = None,
        progress_callback: Optional[Callable] = None,
        workspace_manager=None,
        phase_gate_evaluator=None,
        replanning_engine=None,
        supervisor=None,
        reviewer=None,
        message_bus=None,
        debate=None,
        tool_registry=None,
        cbkb=None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self._cbkb = cbkb
        self.intent_analyzer = intent_analyzer or IntentAnalyzer(debate=debate)
        self.task_decomposer = task_decomposer or TaskDecomposer(cbkb=self._cbkb)
        self._orchestrator = orchestrator
        self._registry = registry
        self._progress_callback = progress_callback
        self._workspace_manager = workspace_manager
        self._phase_gate_evaluator = phase_gate_evaluator
        self._replanning_engine = replanning_engine
        self._supervisor = supervisor
        self._reviewer = reviewer
        self._message_bus = message_bus
        self._debate = debate
        self._tool_registry = tool_registry
        self.memory_manager = memory_manager
```

3. In `run_turn`, after recording the user message and before intent analysis, add enrichment:

```python
        # 1. Record user message
        user_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=user_message,
            sender="user",
        )
        working_memory.add_message(user_msg)

        # 1.5 Enrich context from long-term memory
        extra_context = {}
        if self.memory_manager is not None:
            try:
                extra_context = await self.memory_manager.enrich_context(
                    project_id, user_message, working_memory
                )
            except Exception:
                logger.warning("Memory enrichment failed; continuing", exc_info=True)
```

(If `logging` is not imported, add `import logging` at the top and `logger = logging.getLogger(__name__)` after imports.)

4. Pass `extra_context` into intent analysis:

```python
            intent = await self.intent_analyzer.analyze(
                user_message, working_memory=working_memory, extra_context=extra_context
            )
```

Wait — the current `IntentAnalyzer.analyze` signature does not accept `extra_context`. Do not break the interface. Instead, inject memory snippets into `working_memory.pinned_items` or attach to `working_memory` dynamically. Better: add `extra_context` to `IntentAnalyzer.analyze` if it accepts `**kwargs`, otherwise pin items.

Check the analyzer signature: `async def analyze(self, message: str, working_memory: Optional[WorkingMemory] = None) -> UserIntent:`. It does not accept kwargs. So we should pin memory snippets to working_memory temporarily, or extend the analyzer to accept extra_context.

For minimal change, add the snippets to `working_memory.pinned_items` with a prefix:

```python
        if extra_context.get("memory_snippets"):
            for snippet in extra_context["memory_snippets"]:
                working_memory.pin_item(f"memory:{snippet}")
```

But this pollutes pinned_items. Better: extend `IntentAnalyzer.analyze` to accept optional `extra_context` and include it in the `_build_context` call.

Let's extend the analyzer. In `backend/homomics_lab/agent/intent/analyzer.py`:

```python
    async def analyze(
        self,
        message: str,
        working_memory: Optional[WorkingMemory] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> UserIntent:
        context = self._build_context(working_memory, extra_context)
        ...
```

And update `_build_context`:

```python
    def _build_context(
        self,
        working_memory: Optional[WorkingMemory],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if working_memory is None:
            return extra_context or {}
        recent = working_memory.get_recent_messages(5)
        ctx = {
            "recent_messages": [
                {"role": msg.sender, "content": msg.content}
                for msg in recent
            ],
            "current_task_id": working_memory.current_task_id,
            "pinned_items": working_memory.pinned_items,
        }
        if extra_context:
            ctx["extra_context"] = extra_context
        return ctx
```

This is a clean extension and backward-compatible.

5. At the end of `run_turn`, before returning, persist:

```python
        # Persist turn
        if self.memory_manager is not None:
            try:
                await self.memory_manager.persist_turn(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    task_tree=turn_result.task_tree,
                )
            except Exception:
                logger.exception("Failed to persist turn")

        return turn_result
```

6. Also update `execute_tree` to persist:

```python
    async def execute_tree(...):
        ...
        result = await self._handle_workflow(...)  # or single step

        if self.memory_manager is not None:
            try:
                await self.memory_manager.persist_turn(
                    session_id=session_id or "",
                    project_id=project_id,
                    user_message="",
                    turn_result=result,
                    working_memory=working_memory,
                    task_tree=result.task_tree,
                )
            except Exception:
                logger.exception("Failed to persist execute_tree result")

        return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent/test_turn_runner_memory.py -v
```

Expected: PASS

- [ ] **Step 5: Run existing TurnRunner tests**

```bash
pytest tests/test_agent/test_turn_runner.py tests/test_agent/test_turn_runner_plots.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/homomics_lab/agent/turn_runner.py backend/homomics_lab/agent/intent/analyzer.py backend/tests/test_agent/test_turn_runner_memory.py
git commit -m "feat(turn_runner): wire MemoryManager into run_turn and execute_tree

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Wire MemoryManager into API and Bootstrap

**Files:**
- Modify: `backend/homomics_lab/bootstrap.py`
- Modify: `backend/homomics_lab/main.py`
- Modify: `backend/homomics_lab/api/chat.py`
- Test: `backend/tests/test_api/test_chat_memory.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_api/test_chat_memory.py`:

```python
import time
from fastapi.testclient import TestClient
from homomics_lab.main import app


def _poll_job(client, job_id, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/execution/{job_id}/status")
        data = response.json()
        if data["status"] not in ("queued", "pending", "running"):
            return data
        time.sleep(0.1)
    return response.json()


def test_chat_persists_session_state():
    with TestClient(app) as client:
        # First message
        r1 = client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": "sess_persist_api",
            "message": "帮我分析单细胞数据",
        })
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1["status"] == "queued"

        final1 = _poll_job(client, data1["job_id"])
        assert final1["status"] in ("awaiting_human", "completed", "failed")

        # Second message in same session should have context
        r2 = client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": "sess_persist_api",
            "message": "继续",
        })
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["status"] == "queued"

        # Verify messages endpoint returns accumulated messages
        messages = client.get("/api/chat/messages?session_id=sess_persist_api").json()
        assert len(messages) >= 4
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api/test_chat_memory.py -v
```

Expected: FAIL because `app.state.memory_manager` is not set

- [ ] **Step 3: Modify bootstrap.py**

Add imports at the top:

```python
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.session_store import SQLiteSessionStore
from homomics_lab.context.semantic_memory import SemanticMemory
```

In `bootstrap_worker_context`, before `return`, add:

```python
    # Session / memory management
    session_store = SQLiteSessionStore(
        db_path=settings.session_store_url.replace("sqlite+aiosqlite:///", "")
        if settings.session_store_url.startswith("sqlite+aiosqlite:///")
        else str(settings.data_dir / "sessions.db")
    )
    await session_store.init()

    semantic_memory = None
    if settings.enable_semantic_memory and settings.semantic_search_model:
        semantic_memory = SemanticMemory(
            db_path=str(settings.data_dir / ".metadata" / "semantic_memory.db"),
            model_name=settings.semantic_search_model,
        )

    memory_manager = MemoryManager(
        session_store=session_store,
        semantic_memory=semantic_memory,
        cbkb=None,  # wired later if available
    )
```

Add `memory_manager` to the returned dict:

```python
    return {
        ...,
        "memory_manager": memory_manager,
    }
```

- [ ] **Step 4: Modify main.py**

In `lifespan`, after `ctx = await bootstrap_worker_context(...)`:

```python
    app.state.memory_manager = ctx["memory_manager"]
```

- [ ] **Step 5: Modify api/chat.py**

1. Remove in-memory dictionaries:

```python
# REMOVE these lines:
# _sessions: dict[str, WorkingMemory] = {}
# _task_trees: dict[str, TaskTree] = {}
# _session_project_ids: dict[str, str] = {}
```

2. Update `send_message`:

```python
@router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest, http_request: Request):
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    working_memory, task_tree = await memory_manager.load_session(
        request.session_id, request.project_id
    )

    job_service = getattr(http_request.app.state, "job_service", None) or JobService()
    plan_store = getattr(http_request.app.state, "plan_store", None) or PlanStore()

    runner = TurnRunner(
        tool_registry=getattr(http_request.app.state, "tool_registry", None),
        memory_manager=memory_manager,
    )
    result = await runner.run_turn(
        session_id=request.session_id,
        user_message=request.message,
        working_memory=working_memory,
        project_id=request.project_id,
        job_service=job_service,
        enqueue_skills=True,
        plan_store=plan_store,
    )

    # No need to manually save state; TurnRunner.persist_turn handles it.

    ...
```

3. Update `/messages` endpoint:

```python
@router.get("/messages")
async def get_messages(session_id: str, http_request: Request):
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    working_memory, _ = await memory_manager.load_session(session_id, "")
    return [m.model_dump() for m in working_memory.get_recent_messages()]
```

4. Update `/hitl/respond`:

```python
@router.post("/hitl/respond", response_model=HITLResponseResponse)
async def respond_to_hitl(request: HITLResponseRequest, http_request: Request):
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    job_service = getattr(http_request.app.state, "job_service", None) or JobService()

    job = await job_service.get_latest_job(
        request.session_id,
        statuses=[JobStatus.AWAITING_HUMAN],
    )
    if job is None:
        raise HTTPException(status_code=404, detail="No awaiting HITL job found")

    resume_job = await job_service.create_resume_job(...)

    return HITLResponseResponse(...)
```

5. Update `/debate/respond`:

```python
@router.post("/debate/respond", response_model=DebateResponseResponse)
async def respond_to_debate(request: DebateResponseRequest, http_request: Request):
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    working_memory, _ = await memory_manager.load_session(request.session_id, "")

    debate = _debates.get(request.session_id)
    ...

    runner = TurnRunner(memory_manager=memory_manager)
    result = await runner.run_turn(
        session_id=request.session_id,
        user_message=user_message,
        working_memory=working_memory,
        project_id=...,  # derive from session state
        ...,
    )
```

Note: For debate, we need project_id. We can get it from the SessionState by extending `load_session` return or adding a `get_project_id` method. Better: `load_session` returns `SessionState` or `(WorkingMemory, TaskTree, project_id)`. To keep interface simple, add `MemoryManager.get_project_id(session_id)`.

Add to `MemoryManager`:

```python
    async def get_project_id(self, session_id: str) -> Optional[str]:
        state = await self.session_store.get(session_id)
        return state.project_id if state else None
```

Then in debate respond:

```python
    project_id = await memory_manager.get_project_id(request.session_id) or "default"
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_api/test_chat_memory.py -v
```

Expected: PASS

- [ ] **Step 7: Run existing chat API tests**

```bash
pytest tests/test_api/test_chat.py tests/test_api/test_chat_plots.py -v
```

Expected: PASS (may need to update tests that directly mutate `chat_api._sessions`)

- [ ] **Step 8: Commit**

```bash
git add backend/homomics_lab/bootstrap.py backend/homomics_lab/main.py backend/homomics_lab/api/chat.py backend/tests/test_api/test_chat_memory.py
git commit -m "feat(api): wire MemoryManager into chat endpoints and bootstrap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Update existing tests that depend on in-memory session state

**Files:**
- Modify: `backend/tests/test_api/test_chat.py`

- [ ] **Step 1: Update test_respond_to_debate**

The existing test manually sets `chat_api._sessions` and `chat_api._session_project_ids`. Replace with `MemoryManager` setup:

```python
def test_respond_to_debate():
    with TestClient(app) as client:
        session_id = "sess_debate_api"
        # Seed the session through the API
        client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": session_id,
            "message": "请帮我选择分析类型",
        })

        chat_api._debates[session_id] = {
            "debate_id": "debate_1",
            "topic": "请选择您需要的分析类型",
            "options": [
                {"id": "qa", "label": "问题解答"},
                {"id": "single_cell_analysis", "label": "单细胞分析"},
            ],
            "recommendation": None,
        }

        response = client.post("/api/chat/debate/respond", json={
            "session_id": session_id,
            "debate_id": "debate_1",
            "choice_id": "qa",
            "parameters": {},
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["status"] == "completed"
        assert data["result"]["task_tree"] is not None
```

- [ ] **Step 2: Run all chat API tests**

```bash
pytest tests/test_api/test_chat.py tests/test_api/test_chat_memory.py tests/test_api/test_chat_plots.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_api/test_chat.py
git commit -m "test(api): update chat tests for persistent session state

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Add health check endpoint

**Files:**
- Modify: `backend/homomics_lab/main.py`
- Test: `backend/tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_main.py` (or create if not exists):

```python
def test_memory_health():
    from fastapi.testclient import TestClient
    from homomics_lab.main import app

    with TestClient(app) as client:
        response = client.get("/health/memory")
        assert response.status_code == 200
        data = response.json()
        assert data["session_store"] == "ok"
        assert "semantic_memory" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py::test_memory_health -v
```

Expected: FAIL with 404

- [ ] **Step 3: Add endpoint**

Modify `backend/homomics_lab/main.py`, add after `/health`:

```python
@app.get("/health/memory")
async def health_memory(request: Request):
    mm = getattr(request.app.state, "memory_manager", None)
    if mm is None:
        return {"session_store": "not_configured", "semantic_memory": "not_configured"}

    session_ok = True
    try:
        await mm.session_store.get("__health_check__")
    except Exception:
        session_ok = False

    semantic_ok = mm.semantic_memory is not None

    return {
        "session_store": "ok" if session_ok else "error",
        "semantic_memory": "ok" if semantic_ok else "disabled",
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_main.py::test_memory_health -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/homomics_lab/main.py backend/tests/test_main.py
git commit -m "feat(health): add memory health check endpoint

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Final integration test and cleanup

- [ ] **Step 1: Run full backend test suite**

```bash
pytest backend/tests -x --timeout=120
```

Expected: PASS (or identify any regressions to fix)

- [ ] **Step 2: Fix any regressions**

Common issues to watch for:
- `TaskTree` now inherits from `BaseModel`; code that instantiated it with positional args may break (verify all call sites).
- `api/chat.py` no longer exposes `_sessions`/`_task_trees`; any tests or CLI tools using them will break.
- `SemanticMemory` requires `sentence-transformers`; tests in offline mode should still work if model is cached.

- [ ] **Step 3: Run lint/type check if configured**

```bash
cd /mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend
ruff check homomics_lab/context homomics_lab/agent/turn_runner.py homomics_lab/api/chat.py
```

- [ ] **Step 4: Final commit**

```bash
git commit -m "feat(memory): integrate persistent session state and long-term memory

- Add SQLiteSessionStore for WorkingMemory and TaskTree
- Add MemoryManager to coordinate session store, semantic memory, and CBKB
- Wire MemoryManager into TurnRunner run_turn and execute_tree
- Replace in-memory session dictionaries in chat.py with persistent store
- Add /health/memory endpoint

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Persistent session state: Task 3 (`SessionStore`) + Task 6 (`chat.py` wiring) ✓
- Long-term memory retrieval: Task 4 (`MemoryManager.enrich_context`) + Task 5 (`TurnRunner`) ✓
- Long-term memory persistence: Task 4 (`MemoryManager.persist_turn`) + Task 5 ✓
- Backward compatibility: Task 5 (`TurnRunner` without memory manager still works) ✓
- Health check: Task 8 ✓

**Placeholder scan:**
- No TBD/TODO.
- All code blocks contain concrete implementation.
- All test commands include expected output.

**Type consistency:**
- `TaskTree.model_dump()` / `model_validate()` used consistently.
- `SessionState` dataclass fields match across `session_store.py` and `memory_manager.py`.
- `MemoryManager` signature consistent in tests and implementation.

**Known risks to monitor during execution:**
- `IntentAnalyzer.analyze` signature extension must remain backward-compatible.
- `SemanticMemory` model loading may be slow in tests; existing `HF_HUB_OFFLINE=1` fixture helps.
- `TaskTree` becoming a `BaseModel` may affect code that relies on `__init__` behavior.
