"""Tests for cross-domain plan composition."""

import pytest

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.cross_domain_planner import CrossDomainPlanner
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.config import settings
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


def _make_skill(skill_id: str, category: str) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        version="1.0",
        category=category,
        description=f"Skill {skill_id}",
        input_schema=SkillInputSchema(),
    )


@pytest.fixture
def registry_with_domains() -> SkillRegistry:
    reg = SkillRegistry()
    for skill_id, category in [
        ("sc_data_io", "single-cell-transcriptomics"),
        ("sc_qc", "single-cell-transcriptomics"),
        ("sc_normalize", "single-cell-transcriptomics"),
        ("spatial_data_io", "spatial-transcriptomics"),
        ("spatial_qc", "spatial-transcriptomics"),
        ("spatial_deconv", "spatial-transcriptomics"),
    ]:
        reg.register(_make_skill(skill_id, category))
    return reg


@pytest.fixture
def plan_engine(registry_with_domains, monkeypatch):
    # Domain strategies are disabled by default in tests; enable them so the
    # PlanEngine can return real domain skeletons instead of the generic fallback.
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    return PlanEngine(skill_registry=registry_with_domains)


@pytest.mark.asyncio
async def test_cross_domain_planner_composes_two_domains(plan_engine):
    planner = CrossDomainPlanner(plan_engine=plan_engine)
    intent = UserIntent(
        analysis_type="cross_domain_analysis",
        complexity="complex",
        sub_intents=[
            UserIntent(
                analysis_type="single_cell_analysis",
                complexity="complex",
                domain="single-cell-transcriptomics",
            ),
            UserIntent(
                analysis_type="spatial_analysis",
                complexity="complex",
                domain="spatial-transcriptomics",
            ),
        ],
    )

    plan = await planner.plan(intent)

    assert plan is not None
    assert plan.derivation == "cross-domain-composition"
    assert plan.risk_level == "medium"
    assert plan.approval_required is True
    phase_types = [p.phase_type for p in plan.phases]
    # Both domains contribute phases; overlap phases appear once.
    assert "data_io" in phase_types or "qc" in phase_types
    assert any(
        any("spatial" in d or "single-cell" in d for d in p.merged_from_domains)
        for p in plan.phases
    )


@pytest.mark.asyncio
async def test_cross_domain_planner_ignores_single_domain(plan_engine):
    planner = CrossDomainPlanner(plan_engine=plan_engine)
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
        domain="single-cell-transcriptomics",
    )

    plan = await planner.plan(intent)

    assert plan is None


@pytest.mark.asyncio
async def test_cross_domain_planner_deduplicates_overlapping_phases(plan_engine):
    planner = CrossDomainPlanner(plan_engine=plan_engine)
    intent = UserIntent(
        analysis_type="cross_domain_analysis",
        complexity="complex",
        sub_intents=[
            UserIntent(
                analysis_type="single_cell_analysis",
                complexity="complex",
                domain="single-cell-transcriptomics",
            ),
            UserIntent(
                analysis_type="spatial_analysis",
                complexity="complex",
                domain="spatial-transcriptomics",
            ),
        ],
    )

    plan = await planner.plan(intent)

    phase_types = [p.phase_type for p in plan.phases]
    # data_io / qc should appear at most once across the merged plan.
    assert phase_types.count("data_io") <= 1
    assert phase_types.count("qc") <= 1
