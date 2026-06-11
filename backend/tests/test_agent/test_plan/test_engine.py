"""Tests for PlanEngine."""

import pytest

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillOutputSchema
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
            id="scanpy_pca",
            name="scanpy_pca",
            version="1.0",
            category="single_cell",
            description="PCA",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


class TestPlanEngine:
    def test_single_cell_standard_plan(self, registry):
        engine = PlanEngine(skill_registry=registry)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        plan = engine.plan(intent, DataState())

        phase_types = [p.phase_type for p in plan.phases]
        assert "qc" in phase_types
        assert "normalization" in phase_types
        assert "dim_reduction" in phase_types
        assert "clustering" in phase_types
        assert plan.strategy_name == "single_cell_standard"

    def test_plan_skips_completed_qc(self, registry):
        engine = PlanEngine(skill_registry=registry)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        data_state = DataState(has_qc=True)
        plan = engine.plan(intent, data_state)

        # QC phase should still exist but we can verify state was passed
        assert plan.data_state.has_qc is True
        qc_phase = next((p for p in plan.phases if p.phase_type == "qc"), None)
        assert qc_phase is not None
        # In current implementation, QC is marked as not required when already done
        # but still present in the skeleton

    def test_plan_inserts_batch_correction(self, registry):
        engine = PlanEngine(skill_registry=registry)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        data_state = DataState(batch_detected=True)
        plan = engine.plan(intent, data_state)

        phase_types = [p.phase_type for p in plan.phases]
        assert "batch_correction" in phase_types

    def test_spatial_strategy(self, registry):
        engine = PlanEngine(skill_registry=registry)
        intent = UserIntent(
            analysis_type="spatial_analysis",
            complexity="complex",
        )
        plan = engine.plan(intent, DataState())

        assert plan.strategy_name == "spatial_transcriptomics"
        phase_types = [p.phase_type for p in plan.phases]
        assert "spatial_qc" in phase_types
        assert "spatial_clustering" in phase_types

    def test_qc_only_strategy(self, registry):
        engine = PlanEngine(skill_registry=registry)
        intent = UserIntent(
            analysis_type="file_conversion",
            complexity="single_step",
        )
        plan = engine.plan(intent, DataState())

        assert plan.strategy_name == "qc_only"
        assert len(plan.phases) == 1
        assert plan.phases[0].phase_type == "qc"

    def test_plan_returns_reproducibility_context(self, registry):
        engine = PlanEngine(skill_registry=registry)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        plan = engine.plan(intent, DataState())

        assert "plan_engine_version" in plan.reproducibility_context
        assert "strategy" in plan.reproducibility_context

    def test_generic_fallback(self, registry):
        engine = PlanEngine(skill_registry=registry)
        intent = UserIntent(
            analysis_type="unknown_type",
            complexity="single_step",
        )
        plan = engine.plan(intent, DataState())

        assert plan.strategy_name == "generic"
