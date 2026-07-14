"""Tests for ModeSelector's learned mode-selection prior."""

import pytest

from homomics_lab.agent.plan.mode_selector import ModeSelector
from homomics_lab.agent.plan.mode_selection_lore import (
    IntentFeatures,
    ModeSelectionLore,
)
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.skills.models import SkillDefinition


def _skill(skill_id: str = "curated_step") -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        version="1.0",
        category="general",
    )


def _plan(
    n_phases: int = 4,
    n_covered: int = 4,
    strategy_name: str = "test",
    intent: str = "",
    skill_id: str = "curated_step",
) -> PlanResult:
    phases = [
        Phase(
            phase_type=f"phase_{i}",
            selected_skill=_skill(skill_id) if i < n_covered else None,
        )
        for i in range(n_phases)
    ]
    reproducibility_context = {"intent": intent} if intent else {}
    return PlanResult(
        phases=phases,
        strategy_name=strategy_name,
        data_state=DataState(),
        reproducibility_context=reproducibility_context,
    )


def _features(plan: PlanResult) -> IntentFeatures:
    return ModeSelector.extract_intent_features(plan)


@pytest.fixture
def lore(tmp_path):
    return ModeSelectionLore(db_path=tmp_path / "mode_selection_lore.db")


class TestLoreStorage:
    def test_empty_lore_returns_no_recommendation(self, lore):
        features = IntentFeatures(
            domain="test",
            phase_count=4,
            top_intent="test",
            required_skills=("curated_step",) * 4,
        )
        mode, confidence = lore.get_recommendation(features)
        assert mode is None
        assert confidence == 0.0

    def test_record_increments_weighted_counts(self, lore):
        features = IntentFeatures(
            domain="test",
            phase_count=2,
            top_intent="test",
            required_skills=("s1", "s2"),
        )
        lore.record(features, "fixed_pipeline", outcome_score=2.0)
        lore.record(features, "fixed_pipeline", outcome_score=1.0)
        lore.record(features, "codeact", outcome_score=1.0)

        mode, confidence = lore.get_recommendation(features, min_samples=0)
        assert mode == "fixed_pipeline"
        assert confidence == pytest.approx(3.0 / 4.0)

    def test_min_samples_threshold_is_respected(self, lore):
        features = IntentFeatures(
            domain="test",
            phase_count=1,
            top_intent="test",
            required_skills=("s1",),
        )
        lore.record(features, "codeact")
        mode, confidence = lore.get_recommendation(features, min_samples=2)
        assert mode is None

    def test_confidence_threshold_is_respected(self, lore):
        features = IntentFeatures(
            domain="test",
            phase_count=1,
            top_intent="test",
            required_skills=("s1",),
        )
        lore.record(features, "fixed_pipeline")
        lore.record(features, "codeact")
        mode, confidence = lore.get_recommendation(
            features, min_samples=0, confidence_threshold=0.7
        )
        # Best mode has only 50% weight -> below threshold.
        assert mode is None
        assert confidence == pytest.approx(0.5)


class TestModeSelectorFallback:
    def test_empty_lore_falls_back_to_heuristic_fixed(self, lore):
        selector = ModeSelector(lore=lore)
        plan = _plan(n_phases=4, n_covered=4)
        assert selector.select(plan) == "fixed_pipeline"

    def test_empty_lore_falls_back_to_heuristic_auto(self, lore):
        selector = ModeSelector(lore=lore)
        plan = _plan(n_phases=4, n_covered=2)
        assert selector.select(plan) == "auto"


class TestModeSelectorLearnedPrior:
    def test_recorded_mode_overrides_heuristic(self, lore):
        # A fully-covered plan would normally be fixed_pipeline.
        plan = _plan(n_phases=4, n_covered=4)
        features = _features(plan)
        for _ in range(5):
            lore.record(features, "codeact")

        selector = ModeSelector(
            lore=lore,
            lore_confidence_threshold=0.7,
            lore_min_samples=3,
        )
        assert selector.select(plan) == "codeact"

    def test_different_features_do_not_contaminate(self, lore):
        plan_a = _plan(n_phases=4, n_covered=4, strategy_name="strategy_a")
        plan_b = _plan(n_phases=4, n_covered=4, strategy_name="strategy_b")

        for _ in range(5):
            lore.record(_features(plan_a), "codeact")

        selector = ModeSelector(
            lore=lore,
            lore_confidence_threshold=0.7,
            lore_min_samples=3,
        )
        # plan_b has no lore entry -> heuristic applies.
        assert selector.select(plan_b) == "fixed_pipeline"

    def test_lore_can_switch_recommendation_after_new_observations(self, lore):
        plan = _plan(n_phases=4, n_covered=4)
        features = _features(plan)
        for _ in range(5):
            lore.record(features, "fixed_pipeline")

        selector = ModeSelector(
            lore=lore,
            lore_confidence_threshold=0.7,
            lore_min_samples=3,
        )
        assert selector.select(plan) == "fixed_pipeline"

        # New observations flip the recommendation.
        for _ in range(12):
            lore.record(features, "codeact")

        mode, confidence = lore.get_recommendation(features, min_samples=0)
        assert mode == "codeact"
        assert confidence > 0.7
        assert selector.select(plan) == "codeact"


class TestModeSelectorExplain:
    def test_explain_reports_lore_confidence(self, lore):
        plan = _plan(n_phases=4, n_covered=2)
        selector = ModeSelector(lore=lore)
        lines = " ".join(selector.explain(plan))
        assert "lore_confidence=" in lines

    def test_explain_reports_lore_recommendation(self, lore):
        plan = _plan(n_phases=4, n_covered=4)
        for _ in range(5):
            lore.record(_features(plan), "codeact")
        selector = ModeSelector(
            lore=lore,
            lore_confidence_threshold=0.7,
            lore_min_samples=3,
        )
        lines = " ".join(selector.explain(plan))
        assert "lore_recommendation=codeact" in lines
