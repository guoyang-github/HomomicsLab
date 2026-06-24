"""Tests for TurnRunner risk evaluation and HITL context propagation."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.context.working_memory import WorkingMemory


@pytest.fixture
def runner():
    return TurnRunner()


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.mark.asyncio
async def test_evaluate_risk_heuristic_high_risk(runner, working_memory):
    intent = UserIntent(analysis_type="general", complexity="single_step", confidence=0.9)
    score = await runner._evaluate_risk(
        intent,
        user_message="delete all old files and overwrite results",
        working_memory=working_memory,
        project_id="proj_1",
    )
    assert score > 0.0


@pytest.mark.asyncio
async def test_evaluate_risk_heuristic_low_risk(runner, working_memory):
    intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex", confidence=0.9)
    score = await runner._evaluate_risk(
        intent,
        user_message="run qc and plot UMAP",
        working_memory=working_memory,
        project_id="proj_1",
    )
    assert score == 0.0


@pytest.mark.asyncio
async def test_evaluate_risk_uses_llm_when_available(runner, working_memory):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(return_value='{"risk_score": 0.85}')
    runner._llm_client = mock_client

    intent = UserIntent(analysis_type="general", complexity="single_step", confidence=0.9)
    score = await runner._evaluate_risk(
        intent,
        user_message="drop the whole dataset",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert score == pytest.approx(0.85)
    mock_client.chat_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_risk_falls_back_when_llm_fails(runner, working_memory):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    runner._llm_client = mock_client

    intent = UserIntent(analysis_type="general", complexity="single_step", confidence=0.9)
    score = await runner._evaluate_risk(
        intent,
        user_message="remove everything",
        working_memory=working_memory,
        project_id="proj_1",
    )

    # Should fall back to heuristic and detect high-risk keywords.
    assert score > 0.0


@pytest.mark.asyncio
async def test_build_orchestrator_context_propagates_confidence(runner, working_memory):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="single_step",
        confidence=0.5,
    )
    context = await runner._build_orchestrator_context(
        project_id="proj_1",
        intent=intent,
        user_message="analyze data",
        working_memory=working_memory,
    )
    assert context["confidence"] == 0.5
    assert context["confidence_threshold"] == 0.7


@pytest.mark.asyncio
async def test_build_orchestrator_context_default_values(runner, working_memory):
    context = await runner._build_orchestrator_context(
        project_id="proj_1",
        working_memory=working_memory,
    )
    assert context["confidence"] == 1.0
    assert context["risk_score"] == 0.0
    assert "risk_threshold" in context
    assert "confidence_threshold" in context
