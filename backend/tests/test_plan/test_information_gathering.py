"""Tests for active information gathering."""

import pytest

from homomics_lab.agent.information_gathering import InformationGatheringEngine
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.agent.plan.strategies import AnalysisStrategy, StrategyLibrary
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def registry():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            description="Quality control",
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="metadata_inspector",
            name="metadata_inspector",
            version="1.0",
            category="metadata",
            description="Inspect dataset metadata",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.fixture
def strategy_library():
    lib = StrategyLibrary()
    lib.register(
        AnalysisStrategy(
            name="single_cell_standard",
            description="Standard single-cell analysis",
            applicable_intents=["single_cell_analysis"],
            skeleton=[
                Phase(phase_type="qc", required=True, description="Quality control filtering single-cell RNA-seq scanpy_qc"),
                Phase(phase_type="normalization", required=True, description="Count normalization log transformation single-cell scanpy"),
            ],
            state_checks=[],
        )
    )
    return lib


class TestInformationGatheringEngine:
    def test_decide_probes_for_missing_keys(self, registry):
        engine = InformationGatheringEngine(registry)
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        data_state = DataState()
        probes = engine.decide_probes(intent, data_state)
        missing_keys = {p.missing_key for p in probes}
        assert "organism" in missing_keys
        assert "data_type" in missing_keys
        assert "n_samples" in missing_keys
        assert "batch_info" in missing_keys

    def test_no_probes_when_data_complete(self, registry):
        engine = InformationGatheringEngine(registry)
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        data_state = DataState()
        data_state.set("organism", "human")
        data_state.set("data_type", "scRNA-seq")
        data_state.set("n_samples", 10)
        data_state.set("batch_info", {"batches": 2})
        probes = engine.decide_probes(intent, data_state)
        assert probes == []

    def test_probe_includes_metadata_skill(self, registry):
        engine = InformationGatheringEngine(registry)
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        data_state = DataState()
        probes = engine.decide_probes(intent, data_state)
        skill_ids = {p.skill_id for p in probes}
        assert "metadata_inspector" in skill_ids


class TestPlanEngineInformationRequest:
    @pytest.mark.asyncio
    async def test_information_gathering_disabled_by_default(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        plan = await engine.plan(intent, DataState())
        assert plan.is_information_request is False
        assert len(plan.phases) > 0

    @pytest.mark.asyncio
    async def test_information_request_when_enabled(self, registry, strategy_library):
        engine = PlanEngine(
            skill_registry=registry,
            enable_information_gathering=True,
            strategy_library=strategy_library,
        )
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        plan = await engine.plan(intent, DataState())
        assert plan.is_information_request is True
        assert plan.phases == []
        assert "metadata_inspector" in plan.suggestion_text
        assert "probes" in plan.reproducibility_context

    @pytest.mark.asyncio
    async def test_no_information_request_when_data_complete(self, registry, strategy_library):
        engine = PlanEngine(
            skill_registry=registry,
            enable_information_gathering=True,
            strategy_library=strategy_library,
        )
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        data_state = DataState()
        data_state.set("organism", "human")
        data_state.set("data_type", "scRNA-seq")
        data_state.set("n_samples", 10)
        data_state.set("batch_info", {"batches": 2})
        plan = await engine.plan(intent, data_state)
        assert plan.is_information_request is False
        assert len(plan.phases) > 0
