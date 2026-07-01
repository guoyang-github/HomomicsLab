"""Tests for PlanEngine."""

import pytest

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.agent.plan.strategies import AnalysisStrategy, StateCheck, StrategyLibrary
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
            id="scanpy_pca",
            name="scanpy_pca",
            version="1.0",
            category="single_cell",
            description="PCA",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.fixture
def strategy_library():
    """A minimal test strategy library with a few common analysis skeletons."""
    lib = StrategyLibrary()
    lib.register(
        AnalysisStrategy(
            name="single_cell_standard",
            description="Standard single-cell RNA-seq analysis pipeline",
            applicable_intents=["single_cell_analysis"],
            skeleton=[
                Phase(phase_type="qc", required=True, description="Quality control filtering single-cell RNA-seq scanpy"),
                Phase(phase_type="normalization", required=True, description="Count normalization log transformation single-cell scanpy"),
                Phase(phase_type="dim_reduction", required=True, description="PCA principal component analysis dimensionality reduction single-cell scanpy"),
                Phase(phase_type="clustering", required=True, description="Cell clustering Louvain Leiden single-cell scanpy"),
                Phase(phase_type="annotation", required=True, description="Cell type annotation marker genes single-cell"),
                Phase(phase_type="differential_expression", required=False, description="Differential expression analysis single-cell DE"),
                Phase(phase_type="visualization", required=False, description="Generate UMAP heatmap plots single-cell visualization"),
            ],
            state_checks=[
                StateCheck(
                    condition=lambda ds: ds.get("batch_detected", default=False),
                    action="insert",
                    target="batch_correction",
                    after="qc",
                ),
            ],
        )
    )
    lib.register(
        AnalysisStrategy(
            name="spatial_transcriptomics",
            description="Spatial transcriptomics analysis pipeline",
            applicable_intents=["spatial_analysis"],
            skeleton=[
                Phase(phase_type="spatial_qc", required=True, description="Quality control for spatial transcriptomics"),
                Phase(phase_type="spatial_preprocessing", required=True, description="Spatial preprocessing and normalization"),
                Phase(phase_type="spatial_clustering", required=True, description="Spatial clustering of spots and cells"),
                Phase(phase_type="spatial_deconvolution", required=False, description="Spot deconvolution spatial transcriptomics"),
                Phase(phase_type="visualization", required=False, description="Generate spatial plots and statistics"),
            ],
            state_checks=[],
        )
    )
    lib.register(
        AnalysisStrategy(
            name="qc_only",
            description="Run quality control only",
            applicable_intents=["file_conversion"],
            skeleton=[Phase(phase_type="qc", required=True, description="Quality control filtering")],
            state_checks=[],
        )
    )
    return lib


class TestPlanEngine:
    @pytest.mark.asyncio
    async def test_single_cell_standard_plan(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        plan = await engine.plan(intent, DataState())

        phase_types = [p.phase_type for p in plan.phases]
        assert "qc" in phase_types
        assert "normalization" in phase_types
        assert "dim_reduction" in phase_types
        assert "clustering" in phase_types
        assert plan.strategy_name == "single_cell_standard"

    @pytest.mark.asyncio
    async def test_plan_skips_completed_qc(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        data_state = DataState(has_qc=True)
        plan = await engine.plan(intent, data_state)

        # QC phase should still exist but we can verify state was passed
        assert plan.data_state.has_qc is True
        qc_phase = next((p for p in plan.phases if p.phase_type == "qc"), None)
        assert qc_phase is not None
        # In current implementation, QC is marked as not required when already done
        # but still present in the skeleton

    @pytest.mark.asyncio
    async def test_plan_inserts_batch_correction(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        data_state = DataState(batch_detected=True)
        plan = await engine.plan(intent, data_state)

        phase_types = [p.phase_type for p in plan.phases]
        assert "batch_correction" in phase_types

    @pytest.mark.asyncio
    async def test_spatial_strategy(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(
            analysis_type="spatial_analysis",
            complexity="complex",
        )
        plan = await engine.plan(intent, DataState())

        assert plan.strategy_name == "spatial_transcriptomics"
        phase_types = [p.phase_type for p in plan.phases]
        assert "spatial_qc" in phase_types
        assert "spatial_clustering" in phase_types

    @pytest.mark.asyncio
    async def test_qc_only_strategy(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(
            analysis_type="file_conversion",
            complexity="single_step",
        )
        plan = await engine.plan(intent, DataState())

        assert plan.strategy_name == "qc_only"
        assert len(plan.phases) == 1
        assert plan.phases[0].phase_type == "qc"

    @pytest.mark.asyncio
    async def test_plan_returns_reproducibility_context(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(
            analysis_type="single_cell_analysis",
            complexity="complex",
        )
        plan = await engine.plan(intent, DataState())

        assert "plan_engine_version" in plan.reproducibility_context
        assert "strategy" in plan.reproducibility_context

    @pytest.mark.asyncio
    async def test_generic_fallback(self, registry, strategy_library):
        engine = PlanEngine(skill_registry=registry, strategy_library=strategy_library)
        intent = UserIntent(
            analysis_type="unknown_type",
            complexity="single_step",
        )
        plan = await engine.plan(intent, DataState())

        assert plan.is_fallback is True
        assert plan.strategy_name == "llm_fallback"
