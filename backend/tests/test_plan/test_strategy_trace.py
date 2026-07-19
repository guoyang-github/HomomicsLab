"""Tests for StrategyTrace capture in PlanEngine."""

import pytest

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.plan.strategies import AnalysisStrategy, Phase, StrategyLibrary
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def populated_library(monkeypatch):
    # Disable domain strategy auto-loading so only fixture registrations compete.
    monkeypatch.setattr(StrategyLibrary, "_load_domain_strategies", lambda self: None)
    lib = StrategyLibrary()
    lib.register(
        AnalysisStrategy(
            name="single_cell_standard",
            description="Standard scRNA-seq",
            applicable_intents=["single_cell_analysis"],
            skeleton=[
                Phase(phase_type="qc", required=True),
                Phase(phase_type="normalization", required=True),
            ],
        )
    )
    lib.register(
        AnalysisStrategy(
            name="generic",
            description="Generic flexible",
            applicable_intents=["general"],
            skeleton=[
                Phase(phase_type="data_loading", required=True),
                Phase(phase_type="analysis", required=False),
            ],
        )
    )
    return lib


@pytest.fixture
def skill_registry():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.mark.asyncio
async def test_strategy_trace_populated(populated_library, skill_registry):
    engine = PlanEngine(
        skill_registry=skill_registry,
        strategy_library=populated_library,
    )
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full", confidence=0.9,
        metadata={"reason": "keyword match", "alternatives": []},
    )
    plan = await engine.plan(intent, DataState())

    trace = plan.strategy_trace
    assert trace is not None
    assert trace.intent_analysis_type == "single_cell_analysis"
    assert trace.intent_confidence == 0.9
    assert trace.selected_strategy_name == "single_cell_standard"
    assert len(trace.strategy_candidates) >= 1
    assert any(c["name"] == "single_cell_standard" for c in trace.strategy_candidates)
    assert trace.data_state_snapshot is not None
    assert trace.quality_score is not None


@pytest.mark.asyncio
async def test_explicit_strategy_name_bypasses_selection(populated_library, skill_registry):
    engine = PlanEngine(
        skill_registry=skill_registry,
        strategy_library=populated_library,
    )
    # Use an unknown intent so the default would fall back to generic/llm_fallback;
    # explicit strategy_name forces the chosen strategy.
    intent = UserIntent(intent_type="analysis", interaction_mode="execute", target="unknown_analysis", scope="full", )
    plan = await engine.plan(intent, DataState(), strategy_name="single_cell_standard")

    assert plan.strategy_name == "single_cell_standard"
    trace = plan.strategy_trace
    assert trace.selected_strategy_name == "single_cell_standard"
    assert trace.strategy_candidates[0]["name"] == "single_cell_standard"


@pytest.mark.asyncio
async def test_unknown_strategy_raises(populated_library, skill_registry):
    engine = PlanEngine(
        skill_registry=skill_registry,
        strategy_library=populated_library,
    )
    intent = UserIntent(intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full", )
    with pytest.raises(ValueError, match="Unknown strategy"):
        await engine.plan(intent, DataState(), strategy_name="no_such_strategy")


def test_strategy_trace_serialization_roundtrip():
    from homomics_lab.agent.plan.models import StrategyTrace

    trace = StrategyTrace(
        intent_analysis_type="single_cell_analysis",
        selected_strategy_name="single_cell_standard",
        strategy_candidates=[{"name": "single_cell_standard", "score": 1.5}],
    )
    data = trace.to_dict()
    restored = StrategyTrace.from_dict(data)
    assert restored.intent_analysis_type == "single_cell_analysis"
    assert restored.selected_strategy_name == "single_cell_standard"
    assert restored.strategy_candidates == [{"name": "single_cell_standard", "score": 1.5}]
