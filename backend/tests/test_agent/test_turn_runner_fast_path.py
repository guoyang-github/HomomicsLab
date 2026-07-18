"""Tests for the keyword fast path ahead of context assembly.

A high-confidence keyword direct-answer intent (greeting, simple QA) skips
the three-way context assembly (enrich_context / capability_index.search /
ContextEngine.build); everything else goes through the full assembly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.agent.turn_runner import TurnRunner, ExecutionMode
from homomics_lab.context.working_memory import WorkingMemory


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.fixture
def assembly_mocks():
    memory_manager = MagicMock()
    memory_manager.semantic_memory = None
    memory_manager.enrich_context = AsyncMock(return_value={"memory_snippets": ["snip"]})
    memory_manager.persist_turn = AsyncMock()

    capability_index = MagicMock()
    capability_index.search = AsyncMock(return_value=[])

    context_engine = MagicMock()
    context_engine.build = AsyncMock(return_value=None)

    return memory_manager, capability_index, context_engine


def _make_runner(memory_manager, capability_index, context_engine):
    return TurnRunner(
        memory_manager=memory_manager,
        capability_index=capability_index,
        context_engine=context_engine,
    )


@pytest.mark.asyncio
async def test_fast_path_hit_skips_three_way_assembly(working_memory, assembly_mocks):
    """A high-confidence keyword QA skips all three assembly calls."""
    memory_manager, capability_index, context_engine = assembly_mocks
    runner = _make_runner(memory_manager, capability_index, context_engine)

    result = await runner.run_turn(
        session_id="sess_fast_1",
        user_message="什么是单细胞测序？",
        working_memory=working_memory,
        project_id="proj_1",
    )

    # The turn still answers normally (static QA fallback without an LLM).
    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert "单细胞" in result.response_text or "测序" in result.response_text

    # None of the three assembly sources was touched.
    memory_manager.enrich_context.assert_not_awaited()
    capability_index.search.assert_not_awaited()
    context_engine.build.assert_not_awaited()
    assert runner._extra_context == {}
    assert runner._context_bundle is None

    await runner._state_persistence.drain()


@pytest.mark.asyncio
async def test_fast_path_hit_for_greeting(working_memory, assembly_mocks):
    """A plain greeting takes the fast path and answers normally."""
    memory_manager, capability_index, context_engine = assembly_mocks
    runner = _make_runner(memory_manager, capability_index, context_engine)

    result = await runner.run_turn(
        session_id="sess_fast_2",
        user_message="你好",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.response_text.strip()
    memory_manager.enrich_context.assert_not_awaited()
    capability_index.search.assert_not_awaited()
    context_engine.build.assert_not_awaited()

    await runner._state_persistence.drain()


@pytest.mark.asyncio
async def test_fast_path_miss_runs_full_assembly(working_memory, assembly_mocks):
    """A message without a keyword signal goes through the full assembly."""
    memory_manager, capability_index, context_engine = assembly_mocks
    runner = _make_runner(memory_manager, capability_index, context_engine)

    result = await runner.run_turn(
        session_id="sess_fast_3",
        user_message="zzz qqq xxxx",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    memory_manager.enrich_context.assert_awaited_once()
    capability_index.search.assert_awaited_once()
    context_engine.build.assert_awaited_once()
    # Enrichment results are merged as before.
    assert runner._extra_context["memory_snippets"] == ["snip"]

    await runner._state_persistence.drain()


@pytest.mark.asyncio
async def test_fast_path_miss_for_execution_intent(working_memory, assembly_mocks):
    """Domain workflow keywords never take the fast path (no answer-mode
    structured intent), even at high keyword confidence."""
    memory_manager, capability_index, context_engine = assembly_mocks
    runner = _make_runner(memory_manager, capability_index, context_engine)

    assert await runner._keyword_fast_path_hit("帮我做一个完整的单细胞分析流程") is False


@pytest.mark.asyncio
async def test_keyword_fast_path_probe_hit_and_miss():
    """The probe mirrors the in-analyzer guardrail exactly."""
    runner = TurnRunner()
    assert await runner._keyword_fast_path_hit("什么是单细胞测序？") is True
    assert await runner._keyword_fast_path_hit("你好") is True
    assert await runner._keyword_fast_path_hit("有哪些分析内容") is True
    # No keyword signal.
    assert await runner._keyword_fast_path_hit("zzz qqq") is False
    # Bare analysis verbs route to clarification, never the fast path.
    assert await runner._keyword_fast_path_hit("分析数据") is False


@pytest.mark.asyncio
async def test_keyword_fast_path_probe_requires_builtin_classifier():
    """A custom analyzer without the built-in KeywordIntentClassifier always
    goes through the full assembly (probe returns False)."""
    intent_analyzer = MagicMock()
    runner = TurnRunner(intent_analyzer=intent_analyzer)
    assert await runner._keyword_fast_path_hit("什么是单细胞测序？") is False


@pytest.mark.asyncio
async def test_debate_response_bypasses_fast_path(working_memory, assembly_mocks):
    """Debate-resolved turns skip the probe but still run the full assembly."""
    memory_manager, capability_index, context_engine = assembly_mocks
    runner = _make_runner(memory_manager, capability_index, context_engine)

    result = await runner.run_turn(
        session_id="sess_fast_4",
        user_message="我选择 QA",
        working_memory=working_memory,
        project_id="proj_1",
        debate_response={"choice_id": "qa", "parameters": {}},
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    memory_manager.enrich_context.assert_awaited_once()
    capability_index.search.assert_awaited_once()
    context_engine.build.assert_awaited_once()

    await runner._state_persistence.drain()
