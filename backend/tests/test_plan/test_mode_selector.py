"""Tests for plan-level ModeSelector and its PlanEngine wiring (P3-2)."""

import pytest

from homomics_lab.agent.plan.mode_selector import ModeSelector, VALID_EXECUTION_MODES
from homomics_lab.agent.plan.models import (
    DataState,
    Phase,
    PlannedGap,
    PlanResult,
)
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
    gaps=None,
    risk_level: str = "low",
    is_fallback: bool = False,
    is_information_request: bool = False,
    derivation: str = None,
) -> PlanResult:
    phases = [
        Phase(
            phase_type=f"phase_{i}",
            selected_skill=_skill() if i < n_covered else None,
            derivation=derivation,
        )
        for i in range(n_phases)
    ]
    return PlanResult(
        phases=phases,
        strategy_name="test",
        data_state=DataState(),
        gaps=gaps or [],
        risk_level=risk_level,
        is_fallback=is_fallback,
        is_information_request=is_information_request,
    )


def _gap(gap_type: str = "field_missing") -> PlannedGap:
    return PlannedGap(
        from_phase="a",
        to_phase="b",
        from_skill="s1",
        to_skill="s2",
        gap_type=gap_type,
    )


class TestDecisionRules:
    def test_information_request_stays_auto(self):
        assert ModeSelector().select(_plan(is_information_request=True)) == "auto"

    def test_fallback_plan_goes_codeact(self):
        assert ModeSelector().select(_plan(is_fallback=True)) == "codeact"

    def test_empty_plan_goes_codeact(self):
        assert ModeSelector().select(_plan(n_phases=0, n_covered=0)) == "codeact"

    def test_full_coverage_low_risk_goes_fixed_pipeline(self):
        assert ModeSelector().select(_plan(n_phases=4, n_covered=4)) == "fixed_pipeline"

    def test_standalone_phase_goes_codeact(self):
        plan = _plan(n_phases=4, n_covered=4, derivation="standalone-skill")
        assert ModeSelector().select(plan) == "codeact"

    def test_llm_fallback_phase_goes_codeact(self):
        plan = _plan(n_phases=4, n_covered=4, derivation="llm-fallback")
        assert ModeSelector().select(plan) == "codeact"

    def test_high_risk_blocks_fixed_pipeline(self):
        plan = _plan(n_phases=4, n_covered=4, risk_level="high")
        assert ModeSelector().select(plan) == "auto"

    def test_medium_risk_still_allows_fixed_pipeline(self):
        plan = _plan(n_phases=4, n_covered=4, risk_level="medium")
        assert ModeSelector().select(plan) == "fixed_pipeline"

    def test_low_coverage_goes_codeact(self):
        plan = _plan(n_phases=4, n_covered=1)  # coverage 0.25 < 0.5
        assert ModeSelector().select(plan) == "codeact"

    def test_many_gaps_go_codeact(self):
        plan = _plan(n_phases=4, n_covered=4, gaps=[_gap(), _gap()])
        assert ModeSelector().select(plan) == "codeact"

    def test_none_type_gaps_are_ignored(self):
        plan = _plan(n_phases=4, n_covered=4, gaps=[_gap("none"), _gap("none")])
        assert ModeSelector().select(plan) == "fixed_pipeline"

    def test_middle_ground_is_auto(self):
        plan = _plan(n_phases=4, n_covered=2)  # coverage 0.5, no gaps
        assert ModeSelector().select(plan) == "auto"

    def test_result_is_always_valid(self):
        for plan in (
            _plan(),
            _plan(is_fallback=True),
            _plan(n_phases=0, n_covered=0),
            _plan(n_phases=4, n_covered=1),
            _plan(is_information_request=True),
        ):
            assert ModeSelector().select(plan) in VALID_EXECUTION_MODES


class TestThresholdOverrides:
    def test_custom_thresholds(self):
        selector = ModeSelector(fixed_pipeline_coverage=0.5, max_gaps_for_fixed=1)
        plan = _plan(n_phases=4, n_covered=2, gaps=[_gap()])
        assert selector.select(plan) == "fixed_pipeline"

    def test_invalid_thresholds_raise(self):
        with pytest.raises(ValueError):
            ModeSelector(fixed_pipeline_coverage=0.4, codeact_coverage=0.6)
        with pytest.raises(ValueError):
            ModeSelector(fixed_pipeline_coverage=1.5)


class TestExplain:
    def test_explain_reports_signals(self):
        lines = ModeSelector().explain(_plan(n_phases=4, n_covered=3))
        joined = " ".join(lines)
        assert "coverage=0.75" in joined
        assert "gaps=0" in joined
        assert "risk_level=low" in joined
        assert "selected_mode=auto" in joined


class TestPlanResultField:
    def test_default_is_auto(self):
        assert _plan().execution_mode == "auto"

    def test_serialization_round_trip(self):
        plan = _plan()
        plan.execution_mode = "fixed_pipeline"
        restored = PlanResult.from_dict(plan.to_dict())
        assert restored.execution_mode == "fixed_pipeline"

    def test_from_dict_defaults_when_missing(self):
        plan = _plan()
        data = plan.to_dict()
        del data["execution_mode"]
        assert PlanResult.from_dict(data).execution_mode == "auto"


@pytest.mark.asyncio
async def test_plan_engine_fills_execution_mode():
    """Integration: PlanEngine.plan() populates execution_mode via ModeSelector."""
    from homomics_lab.evaluation.mode_benchmark import _build_full_coverage

    engine, intent, strategy_name = _build_full_coverage()
    plan = await engine.plan(intent, DataState(), strategy_name=strategy_name)
    assert plan.execution_mode == "fixed_pipeline"
