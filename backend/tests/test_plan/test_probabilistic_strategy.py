"""Tests for probabilistic strategy selection."""

import pytest

from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.plan.strategies import (
    SINGLE_CELL_STANDARD,
    StrategyLibrary,
)


class TestStrategyScoring:
    def test_applicable_intent_base_score(self):
        data_state = DataState()
        score = SINGLE_CELL_STANDARD.score("single_cell_analysis", data_state)
        assert score >= 1.0

    def test_keyword_boost(self):
        data_state = DataState()
        # The intent tokens overlap with the strategy corpus (cell, analysis, ...).
        score = SINGLE_CELL_STANDARD.score("single_cell_analysis", data_state)
        assert score > 1.0

    def test_data_state_phase_match_boost(self):
        data_state = DataState()
        data_state.set("qc", True)
        score = SINGLE_CELL_STANDARD.score("single_cell_analysis", data_state)
        assert score > 1.0

    def test_non_applicable_intent_low_score(self):
        data_state = DataState()
        score = SINGLE_CELL_STANDARD.score("unknown_type", data_state)
        assert score < 1.0


class TestStrategyLibrarySelection:
    def test_legacy_select_returns_single_strategy(self):
        lib = StrategyLibrary()
        strategy = lib.select("single_cell_analysis")
        # Domain strategies may override the hard-coded default; accept either.
        assert "single_cell" in strategy.name

    def test_select_with_data_state_returns_single_strategy(self):
        lib = StrategyLibrary()
        strategy = lib.select("spatial_analysis", data_state=DataState())
        assert "spatial" in strategy.name

    def test_select_top_k_returns_ranked_tuples(self):
        lib = StrategyLibrary()
        ranked = lib.select_top_k("single_cell_analysis", DataState(), top_k=3)
        assert len(ranked) <= 3
        assert all(isinstance(item, tuple) and len(item) == 2 for item in ranked)
        assert "single_cell" in ranked[0][0].name
        # Scores should be descending.
        scores = [score for _strategy, score in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_select_top_k_falls_back_to_generic(self):
        lib = StrategyLibrary()
        ranked = lib.select_top_k("unknown_type", DataState(), top_k=3)
        assert ranked[0][0].name == "generic"

    def test_select_with_top_k_one_returns_strategy(self):
        lib = StrategyLibrary()
        result = lib.select("single_cell_analysis", data_state=DataState(), top_k=1)
        assert "single_cell" in result.name

    def test_select_with_top_k_greater_than_one_returns_list(self):
        lib = StrategyLibrary()
        result = lib.select("single_cell_analysis", data_state=DataState(), top_k=2)
        assert isinstance(result, list)
        assert len(result) == 2


class TestPlanEngineBeamSearch:
    @pytest.mark.asyncio
    async def test_top_k_beam_selects_single_cell(self):
        from homomics_lab.agent.intent_analyzer import UserIntent
        from homomics_lab.agent.plan.engine import PlanEngine
        from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
        from homomics_lab.skills.registry import SkillRegistry

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

        engine = PlanEngine(skill_registry=reg)
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        plan = await engine.plan(intent, DataState(), top_k=2)

        assert "single_cell" in plan.strategy_name
        phase_types = [p.phase_type for p in plan.phases]
        assert "qc" in phase_types
