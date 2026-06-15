"""Tests for MemoryManager facade."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.session_store import SessionState, SQLiteSessionStore
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.agent.turn_runner import TurnResult, ExecutionMode
from homomics_lab.tasks.task_tree import TaskTree


@pytest_asyncio.fixture
async def session_store(tmp_path):
    db_path = str(tmp_path / "sessions.db")
    store = SQLiteSessionStore(db_path)
    await store.init()
    return store


@pytest_asyncio.fixture
async def memory_manager(session_store):
    # Mock semantic_memory to avoid loading sentence-transformers
    semantic_memory = MagicMock()
    semantic_memory.search = AsyncMock(return_value=[])
    semantic_memory.add = AsyncMock(return_value="mem_id_1")

    manager = MemoryManager(
        session_store=session_store,
        semantic_memory=semantic_memory,
        cbkb=None,
    )
    return manager


@pytest.mark.asyncio
async def test_load_session_creates_new(memory_manager):
    wm, tree = await memory_manager.load_session("new_sess", "proj_1")
    assert isinstance(wm, WorkingMemory)
    assert tree is None


@pytest.mark.asyncio
async def test_load_session_restores_existing(memory_manager):
    # Save a session directly via store
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="msg_0", type=MessageType.TEXT, content="hello", sender="user"))
    state = SessionState(
        session_id="existing_sess",
        project_id="proj_1",
        working_memory=wm,
        task_tree=None,
        updated_at=datetime.now(timezone.utc),
    )
    await memory_manager.session_store.save(state)

    # Load via manager
    loaded_wm, loaded_tree = await memory_manager.load_session("existing_sess", "proj_1")
    assert isinstance(loaded_wm, WorkingMemory)
    assert len(loaded_wm.messages) == 1
    assert loaded_wm.messages[0].content == "hello"
    assert loaded_tree is None


@pytest.mark.asyncio
async def test_enrich_context_retrieves_semantic_memory(memory_manager):
    memory_manager.semantic_memory.search = AsyncMock(
        return_value=[{"text": "previous QC filtered 12% cells"}]
    )

    wm = WorkingMemory()
    context = await memory_manager.enrich_context("proj_1", "how many cells were filtered", wm)

    assert context["memory_snippets"] == ["previous QC filtered 12% cells"]
    memory_manager.semantic_memory.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_turn_saves_session(memory_manager):
    wm = WorkingMemory()
    agent_msg = ChatMessage(id="msg_1", type=MessageType.TEXT, content="hi", sender="agent")
    turn_result = TurnResult(
        mode=ExecutionMode.DIRECT_RESPONSE,
        response_text="hi",
        task_tree=None,
        agent_message=agent_msg,
    )

    await memory_manager.persist_turn(
        session_id="sess_1",
        project_id="proj_1",
        user_message="hello",
        turn_result=turn_result,
        working_memory=wm,
        task_tree=None,
    )

    # Verify session was saved
    saved_state = await memory_manager.session_store.get("sess_1")
    assert saved_state is not None
    assert saved_state.project_id == "proj_1"
    assert len(saved_state.working_memory.messages) == 1
    assert saved_state.working_memory.messages[0].content == "hi"

    # Verify semantic_memory.add was called
    memory_manager.semantic_memory.add.assert_awaited_once()
    call_kwargs = memory_manager.semantic_memory.add.await_args.kwargs
    assert call_kwargs["memory_type"] == "conversation"
    assert call_kwargs["metadata"]["project_id"] == "proj_1"
