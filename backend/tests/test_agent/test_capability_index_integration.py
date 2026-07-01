"""Integration tests for CapabilityIndex / MemoryBackend wiring in TurnRunner and PlanEngine."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import Phase
from homomics_lab.agent.plan.strategies import AnalysisStrategy, StrategyLibrary
from homomics_lab.agent.retrieval import RetrievalContext, SkillRetriever
from homomics_lab.agent.turn_runner import TurnRunner, ExecutionMode
from homomics_lab.context.feedback_store import FeedbackOutcome
from homomics_lab.agent.plan.models import DataState
from homomics_lab.context.memory_backend import MemoryBackend
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.skills.capability_index import CapabilityCandidate, CapabilityIndex, CapabilityType
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tasks.models import TaskNode, TaskStatus
from homomics_lab.tasks.task_tree import TaskTree


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.fixture
def mock_capability_index():
    idx = MagicMock(spec=CapabilityIndex)
    idx.search = AsyncMock(return_value=[])
    idx.add_feedback = AsyncMock(return_value=None)
    return idx


@pytest.fixture
def mock_memory_backend():
    mb = MagicMock(spec=MemoryBackend)
    mb.add = AsyncMock(return_value="mem-id")
    mb.add_feedback = AsyncMock(return_value=None)
    return mb


@pytest.mark.asyncio
async def test_turn_runner_enriches_context_with_capability_index(
    mock_capability_index, working_memory
):
    """When a CapabilityIndex is wired, TurnRunner should query it during context enrichment."""
    candidate = CapabilityCandidate(
        id="scanpy-qc",
        type=CapabilityType.SKILL,
        name="Scanpy QC",
        description="Quality control for single-cell data",
        category="single-cell",
        score=0.95,
        payload={},
    )
    mock_capability_index.search = AsyncMock(return_value=[candidate])

    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        original_message="how do I filter low quality cells",
    )
    intent_analyzer = MagicMock()
    intent_analyzer.analyze = AsyncMock(return_value=intent)

    runner = TurnRunner(
        capability_index=mock_capability_index,
        intent_analyzer=intent_analyzer,
        llm_client=None,
    )

    result = await runner.run_turn(
        session_id="sess_cap_1",
        user_message="how do I filter low quality cells",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    mock_capability_index.search.assert_awaited_once()
    call_kwargs = mock_capability_index.search.await_args.kwargs
    assert call_kwargs.get("project_id") == "proj_1"
    assert CapabilityType.SKILL in call_kwargs.get("item_types", [])
    assert "capability_candidates" in runner._extra_context
    assert runner._extra_context["capability_candidates"][0]["id"] == "scanpy-qc"


@pytest.mark.asyncio
async def test_turn_runner_records_capability_feedback_after_success(
    mock_capability_index, working_memory
):
    """After a successful skill execution, feedback should be recorded in CapabilityIndex."""
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
    tree.tasks[0].status = TaskStatus.COMPLETED

    orchestrator = MagicMock()
    orchestrator.run_tree = AsyncMock(
        return_value={"t1": {"skill": "scanpy_qc", "result": {"ok": True}}}
    )
    orchestrator.get_progress = MagicMock(return_value={"completed": 1, "total": 1})

    runner = TurnRunner(
        orchestrator=orchestrator,
        capability_index=mock_capability_index,
    )

    result = await runner._handle_single_step(
        tree=tree,
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.SINGLE_STEP
    mock_capability_index.add_feedback.assert_awaited_once()
    call_kwargs = mock_capability_index.add_feedback.await_args.kwargs
    assert call_kwargs["capability_id"] == "scanpy_qc"
    assert call_kwargs["capability_type"] == CapabilityType.SKILL
    assert call_kwargs["outcome"] == FeedbackOutcome.SUCCESS
    assert call_kwargs["project_id"] == "proj_1"


@pytest.mark.asyncio
async def test_turn_runner_records_memory_backend_feedback_after_failure(
    mock_capability_index, mock_memory_backend, working_memory
):
    """After a failed skill execution, a task memory and capability feedback should be recorded."""
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
    tree.tasks[0].status = TaskStatus.FAILED

    orchestrator = MagicMock()
    orchestrator.run_tree = AsyncMock(
        return_value={"t1": {"skill": "scanpy_qc", "error": "matrix too small"}}
    )
    orchestrator.get_progress = MagicMock(return_value={"completed": 0, "total": 1})

    runner = TurnRunner(
        orchestrator=orchestrator,
        capability_index=mock_capability_index,
        memory_backend=mock_memory_backend,
    )

    await runner._handle_single_step(
        tree=tree,
        working_memory=working_memory,
        project_id="proj_1",
    )

    mock_capability_index.add_feedback.assert_awaited_once()
    assert mock_capability_index.add_feedback.await_args.kwargs["outcome"] == FeedbackOutcome.FAILURE
    mock_memory_backend.add.assert_awaited_once()
    assert "scanpy_qc" in mock_memory_backend.add.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_skill_retriever_merges_capability_results():
    """SkillRetriever should merge CapabilityIndex candidates with SkillDAG/registry results."""
    skill = SkillDefinition(
        id="cap-skill-1",
        name="Cap skill",
        version="1.0.0",
        category="test",
        description="A skill discovered via capability index.",
    )
    registry = SkillRegistry()
    registry.register(skill)

    candidate = CapabilityCandidate(
        id="cap-skill-1",
        type=CapabilityType.SKILL,
        name="Cap skill",
        description="A skill discovered via capability index.",
        category="test",
        score=0.88,
        payload={},
    )
    idx = MagicMock(spec=CapabilityIndex)
    idx.search = AsyncMock(return_value=[candidate])

    retriever = SkillRetriever(skill_registry=registry, capability_index=idx)
    context: RetrievalContext = await retriever.retrieve(
        query="test capability",
        intent_type="test",
        project_id="proj_1",
    )

    idx.search.assert_awaited_once()
    skill_ids = [s.skill.id for s in context.skills]
    assert "cap-skill-1" in skill_ids


@pytest.mark.asyncio
async def test_plan_engine_forwards_project_id_to_retriever():
    """PlanEngine should pass project_id through to SkillRetriever when planning."""
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id="scanpy_qc",
            name="Scanpy QC",
            version="1.0.0",
            category="single_cell",
            description="Quality control for single-cell data.",
        )
    )

    idx = MagicMock(spec=CapabilityIndex)
    idx.search = AsyncMock(return_value=[])

    strategy_lib = StrategyLibrary()
    strategy_lib.register(
        AnalysisStrategy(
            name="single_cell_standard",
            description="Standard single-cell analysis",
            applicable_intents=["single_cell_analysis"],
            skeleton=[Phase(phase_type="qc", required=True)],
            state_checks=[],
        )
    )

    retriever = SkillRetriever(skill_registry=registry, capability_index=idx)
    engine = PlanEngine(
        skill_registry=registry,
        skill_retriever=retriever,
        strategy_library=strategy_lib,
    )

    intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
    result = await engine.plan(intent, data_state=DataState(), project_id="proj_42")

    assert result is not None
    idx.search.assert_awaited_once()
    assert idx.search.await_args.kwargs.get("project_id") == "proj_42"


@pytest.mark.asyncio
async def test_backward_compatibility_without_capability_index(working_memory):
    """TurnRunner should still work when no CapabilityIndex is provided."""
    runner = TurnRunner(llm_client=None)
    result = await runner.run_turn(
        session_id="sess_no_cap",
        user_message="什么是 UMAP？",
        working_memory=working_memory,
        project_id="proj_1",
    )
    assert result.mode == ExecutionMode.DIRECT_RESPONSE
