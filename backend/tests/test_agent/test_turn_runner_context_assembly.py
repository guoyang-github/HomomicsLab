"""Tests for concurrent context assembly in TurnRunner._run_turn_once."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.agent.turn_runner import TurnRunner, ExecutionMode
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.session_store import SessionStore
from homomics_lab.context.working_memory import WorkingMemory


class _FakeSessionStore(SessionStore):
    """Minimal in-memory session store for testing."""

    def __init__(self):
        self._data = {}

    async def get(self, session_id: str):
        return self._data.get(session_id)

    async def save(self, state) -> None:
        self._data[state.session_id] = state

    async def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)

    async def cleanup_expired(self, ttl_days: int) -> int:
        return 0

    async def list(self, project_id: str | None = None):
        if project_id is None:
            return list(self._data.values())
        return [s for s in self._data.values() if s.project_id == project_id]


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.mark.asyncio
async def test_gather_single_failure_degrades(working_memory):
    """Each context source fails independently; the turn must still succeed."""
    memory_manager = MagicMock()
    memory_manager.semantic_memory = None
    memory_manager.enrich_context = AsyncMock(side_effect=RuntimeError("enrich down"))
    memory_manager.persist_turn = AsyncMock()

    capability_index = MagicMock()
    capability_index.search = AsyncMock(side_effect=RuntimeError("capability down"))

    context_engine = MagicMock()
    context_engine.build = AsyncMock(side_effect=RuntimeError("build down"))

    runner = TurnRunner(
        memory_manager=memory_manager,
        capability_index=capability_index,
        context_engine=context_engine,
    )
    result = await runner.run_turn(
        session_id="sess_gather_1",
        user_message="什么是单细胞测序？",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    memory_manager.enrich_context.assert_awaited_once()
    capability_index.search.assert_awaited_once()
    context_engine.build.assert_awaited_once()
    # Degraded paths: no extra context and no bundle, but the turn completed.
    assert runner._extra_context == {}
    assert runner._context_bundle is None

    await runner._state_persistence.drain()


@pytest.mark.asyncio
async def test_semantic_search_runs_once_per_turn(working_memory):
    """enrich_context and ContextEngine.build share one semantic search."""
    semantic_memory = MagicMock()
    semantic_memory.search = AsyncMock(return_value=[{"text": "snip", "id": "m1"}])
    semantic_memory.add = AsyncMock(return_value="mem-id")

    memory_manager = MemoryManager(
        session_store=_FakeSessionStore(), semantic_memory=semantic_memory
    )

    context_engine = MagicMock()
    context_engine.build = AsyncMock(return_value=None)

    runner = TurnRunner(memory_manager=memory_manager, context_engine=context_engine)
    user_message = "什么是单细胞测序？"
    result = await runner.run_turn(
        session_id="sess_gather_2",
        user_message=user_message,
        working_memory=working_memory,
        project_id="proj_1",
    )
    assert result.mode == ExecutionMode.DIRECT_RESPONSE

    # Exactly one search for the user message (hoisted, shared); the only
    # other search is the separate "preference" lookup inside enrich_context.
    user_searches = [
        c
        for c in semantic_memory.search.await_args_list
        if c.kwargs.get("query") == user_message or c.args[:1] == (user_message,)
    ]
    assert len(user_searches) == 1

    # The shared result is passed to both consumers.
    context_engine.build.assert_awaited_once()
    assert context_engine.build.await_args.kwargs["prefetched_memories"] == [
        {"text": "snip", "id": "m1"}
    ]
    assert context_engine.build.await_args.kwargs["session_id"] == "sess_gather_2"
    assert runner._extra_context["memory_snippets"] == ["snip"]

    await runner._state_persistence.drain()
