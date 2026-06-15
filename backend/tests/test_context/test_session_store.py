import pytest
import pytest_asyncio
from datetime import datetime, timezone
from homomics_lab.context.session_store import SQLiteSessionStore, SessionState
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.tasks.models import TaskNode, TaskStatus


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(str(db_path))
    await store.init()
    return store


@pytest.mark.asyncio
async def test_save_and_load_session(store):
    # Create WorkingMemory with one message
    wm = WorkingMemory(max_messages=20)
    wm.add_message(ChatMessage(id="msg-1", sender="user", content="hello"))

    # Create TaskTree with one TaskNode
    task = TaskNode(
        id="task-1",
        name="Test Task",
        description="A test task",
        status=TaskStatus.PENDING,
    )
    tree = TaskTree(tasks=[task])

    # Create session state
    state = SessionState(
        session_id="session-1",
        project_id="project-1",
        working_memory=wm,
        task_tree=tree,
        updated_at=datetime.now(timezone.utc),
    )

    # Save and load
    await store.save(state)
    loaded = await store.get("session-1")

    assert loaded is not None
    assert loaded.session_id == "session-1"
    assert loaded.project_id == "project-1"
    assert len(loaded.working_memory.messages) == 1
    assert loaded.working_memory.messages[0].content == "hello"
    assert len(loaded.task_tree.tasks) == 1
    assert loaded.task_tree.tasks[0].id == "task-1"
    assert loaded.task_tree.tasks[0].name == "Test Task"


@pytest.mark.asyncio
async def test_missing_session_returns_none(store):
    loaded = await store.get("non-existent-session")
    assert loaded is None


@pytest.mark.asyncio
async def test_delete_session(store):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="msg-1", sender="user", content="hello"))

    state = SessionState(
        session_id="session-delete",
        project_id="project-1",
        working_memory=wm,
        task_tree=None,
        updated_at=datetime.now(timezone.utc),
    )

    await store.save(state)
    loaded_before = await store.get("session-delete")
    assert loaded_before is not None

    await store.delete("session-delete")
    loaded_after = await store.get("session-delete")
    assert loaded_after is None
