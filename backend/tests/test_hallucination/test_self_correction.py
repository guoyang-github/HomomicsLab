"""Tests for controlled self-correction."""

import pytest

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine, ReplanningTrigger
from homomics_lab.agent.plan.self_correction import (
    SelfCorrectionAction,
    SelfCorrectionEngine,
    SelfCorrectionPolicy,
)
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema


def _make_plan() -> PlanResult:
    skill = SkillDefinition(
        id="scanpy_qc",
        name="QC",
        version="1.0",
        category="single-cell",
        input_schema=SkillInputSchema(),
    )
    return PlanResult(
        phases=[
            Phase(phase_type="qc", required=True, selected_skill=skill),
            Phase(phase_type="normalize", required=True, selected_skill=skill),
        ],
        strategy_name="single-cell-transcriptomics",
        data_state=DataState(),
        derivation="domain-strategy",
        risk_level="low",
    )


@pytest.fixture
def engine():
    replanning = DynamicReplanningEngine(plan_engine=None, skill_dag=None)
    policy = SelfCorrectionPolicy(
        auto_severity=["minor"],
        hitl_severity=["major"],
        stop_severity=["critical"],
    )
    return SelfCorrectionEngine(replanning_engine=replanning, policy=policy)


@pytest.mark.asyncio
async def test_minor_trigger_auto_replan(engine):
    plan = _make_plan()
    triggers = [
        ReplanningTrigger(
            trigger_type="skill_failure",
            severity="minor",
            context={"phase_type": "qc", "reason": "QC timeout"},
        )
    ]

    decision = engine.evaluate(plan, triggers)

    assert decision.action == SelfCorrectionAction.AUTO_REPLAN
    assert decision.severity == "minor"
    assert decision.new_plan is not None


@pytest.mark.asyncio
async def test_major_trigger_requires_hitl(engine):
    plan = _make_plan()
    triggers = [
        ReplanningTrigger(
            trigger_type="skill_failure",
            severity="major",
            context={"phase_type": "qc", "reason": "QC validation failed"},
        )
    ]

    decision = engine.evaluate(plan, triggers)

    assert decision.action == SelfCorrectionAction.HITL_REPLAN
    assert decision.severity == "major"
    assert decision.delta_summary != ""


@pytest.mark.asyncio
async def test_critical_trigger_stops(engine):
    plan = _make_plan()
    triggers = [
        ReplanningTrigger(
            trigger_type="skill_failure",
            severity="critical",
            context={"phase_type": "qc", "reason": "Data corrupted"},
        )
    ]

    decision = engine.evaluate(plan, triggers)

    assert decision.action == SelfCorrectionAction.STOP
    assert decision.new_plan is None


@pytest.mark.asyncio
async def test_no_triggers_returns_unchanged_plan(engine):
    plan = _make_plan()

    decision = engine.evaluate(plan, [])

    assert decision.action == SelfCorrectionAction.AUTO_REPLAN
    assert decision.new_plan is not None
    assert decision.new_plan.phases[0].phase_type == "qc"
