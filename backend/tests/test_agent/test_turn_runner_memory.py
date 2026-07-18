"""Tests for MemoryManager wiring inside TurnRunner."""

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
def semantic_memory():
    """Mocked SemanticMemory that avoids sqlite-vec / sentence-transformers."""
    sm = MagicMock()
    sm.search = AsyncMock(return_value=[])
    sm.add = AsyncMock(return_value="mem-id")
    return sm


@pytest.fixture
def memory_manager(semantic_memory):
    store = _FakeSessionStore()
    return MemoryManager(session_store=store, semantic_memory=semantic_memory)


@pytest.fixture
def runner_with_memory(memory_manager):
    return TurnRunner(memory_manager=memory_manager)


@pytest.fixture
def runner_without_memory():
    return TurnRunner()


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.mark.asyncio
async def test_run_turn_calls_enrich_context_and_persist_turn(
    runner_with_memory, memory_manager, semantic_memory, working_memory
):
    """When memory_manager is provided, run_turn should call enrich_context and persist_turn."""
    # The message carries no keyword-classifier signal, so the keyword fast
    # path does not fire and the full context assembly (enrich_context) runs.
    result = await runner_with_memory.run_turn(
        session_id="sess_mem_1",
        user_message="zzz qqq xxxx",
        working_memory=working_memory,
        project_id="proj_1",
    )

    # Should complete successfully (direct response for QA)
    assert result.mode == ExecutionMode.DIRECT_RESPONSE

    # Persistence is fire-and-forget; wait for the background task to finish.
    await runner_with_memory._state_persistence.drain()

    # enrich_context triggers semantic_memory.search (memory snippets + preferences)
    assert semantic_memory.search.await_count == 2
    search_calls = semantic_memory.search.await_args_list
    project_calls = [c for c in search_calls if c.kwargs.get("project_id") == "proj_1"]
    assert len(project_calls) >= 1

    # persist_turn triggers semantic_memory.add (conversation + possibly preference)
    assert semantic_memory.add.await_count >= 1
    add_calls = [c for c in semantic_memory.add.await_args_list if c.kwargs.get("memory_type") == "conversation"]
    assert add_calls
    assert add_calls[0].kwargs["metadata"]["project_id"] == "proj_1"


@pytest.mark.asyncio
async def test_run_turn_without_memory_manager_works(
    runner_without_memory, working_memory
):
    """TurnRunner without memory_manager should behave exactly as before."""
    result = await runner_without_memory.run_turn(
        session_id="sess_no_mem",
        user_message="什么是单细胞测序？",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert "单细胞" in result.response_text or "测序" in result.response_text


@pytest.mark.asyncio
async def test_enrich_context_failure_is_non_fatal(
    memory_manager, semantic_memory, working_memory
):
    """If enrich_context raises, the turn should continue without extra_context."""
    semantic_memory.search = AsyncMock(side_effect=RuntimeError("DB down"))

    runner = TurnRunner(memory_manager=memory_manager)
    # No keyword-classifier signal → enrich_context actually runs (and fails).
    result = await runner.run_turn(
        session_id="sess_err_1",
        user_message="zzz qqq xxxx",
        working_memory=working_memory,
        project_id="proj_1",
    )

    # Should still succeed (direct response)
    assert result.mode == ExecutionMode.DIRECT_RESPONSE


@pytest.mark.asyncio
async def test_persist_turn_failure_is_non_fatal(
    memory_manager, semantic_memory, working_memory
):
    """If persist_turn raises, the turn should still return its result."""
    semantic_memory.add = AsyncMock(side_effect=RuntimeError("write failed"))

    runner = TurnRunner(memory_manager=memory_manager)
    result = await runner.run_turn(
        session_id="sess_err_2",
        user_message="什么是 UMAP？",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE


@pytest.mark.asyncio
async def test_execute_tree_persists_turn(memory_manager, semantic_memory, working_memory):
    """execute_tree should also call persist_turn when memory_manager is wired."""
    from homomics_lab.tasks.models import TaskNode
    from homomics_lab.tasks.task_tree import TaskTree

    tree = TaskTree(
        tasks=[
            TaskNode(
                id="t1",
                name="qc",
                description="Run QC",
                skills_required=["scanpy_qc"],
            )
        ]
    )

    # Mock orchestrator to avoid actual skill execution
    orchestrator = MagicMock()
    orchestrator.run_tree = AsyncMock(return_value={
        "t1": {"skill": "scanpy_qc", "result": {"output_path": "/tmp/out.h5ad"}}
    })
    orchestrator.get_progress = MagicMock(return_value={"completed": 1, "total": 1})

    runner = TurnRunner(orchestrator=orchestrator, memory_manager=memory_manager)
    result = await runner.execute_tree(
        tree=tree,
        working_memory=working_memory,
        project_id="proj_1",
        session_id="sess_bg_1",
    )

    assert result.mode == ExecutionMode.SINGLE_STEP
    semantic_memory.add.assert_awaited_once()
    add_call = semantic_memory.add.await_args
    assert "Run QC" in add_call.kwargs["text"]
