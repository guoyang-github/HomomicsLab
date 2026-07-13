"""Tests for composite cross-domain planner with bridge skill insertion."""

import pytest

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.composite_planner import CompositePlanner
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.config import settings
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


def _make_skill(
    skill_id: str,
    category: str,
    domains: list = None,
    description: str = "",
    categories: list = None,
) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        version="1.0",
        category=category,
        description=description,
        input_schema=SkillInputSchema(),
        domains=domains or [],
        categories=categories or [],
    )


@pytest.fixture
def cross_domain_intent() -> UserIntent:
    return UserIntent(
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


def _build_registry(include_bridge: bool = True) -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(
        _make_skill("sc_data_io", "single-cell-transcriptomics", ["single-cell-transcriptomics"])
    )
    reg.register(
        _make_skill("sc_qc", "single-cell-transcriptomics", ["single-cell-transcriptomics"])
    )
    reg.register(
        _make_skill("spatial_data_io", "spatial-transcriptomics", ["spatial-transcriptomics"])
    )
    reg.register(
        _make_skill("spatial_deconv", "spatial-transcriptomics", ["spatial-transcriptomics"])
    )
    if include_bridge:
        reg.register(
            _make_skill(
                "sc_to_spatial_bridge",
                "bridge",
                ["single-cell-transcriptomics", "spatial-transcriptomics"],
                description="Bridge single-cell to spatial",
            )
        )
    return reg


@pytest.fixture
def registry_with_bridge() -> SkillRegistry:
    return _build_registry(include_bridge=True)


@pytest.fixture
def registry_without_bridge() -> SkillRegistry:
    return _build_registry(include_bridge=False)


@pytest.mark.asyncio
async def test_composite_planner_inserts_bridge_skill(
    registry_with_bridge, cross_domain_intent, monkeypatch
):
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    engine = PlanEngine(skill_registry=registry_with_bridge)
    planner = CompositePlanner(
        plan_engine=engine,
        skill_registry=registry_with_bridge,
    )
    plan = await planner.plan(cross_domain_intent)

    assert plan is not None
    phase_types = [p.phase_type for p in plan.phases]
    assert "bridge" in phase_types

    bridge_phase = next(p for p in plan.phases if p.phase_type == "bridge")
    assert bridge_phase.selected_skill is not None
    assert bridge_phase.selected_skill.id == "sc_to_spatial_bridge"
    assert bridge_phase.derivation == "cross-domain-bridge"


@pytest.mark.asyncio
async def test_composite_planner_falls_back_to_category_bridge(
    cross_domain_intent, monkeypatch
):
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    reg = SkillRegistry()
    reg.register(
        _make_skill("sc_data_io", "single-cell-transcriptomics", ["single-cell-transcriptomics"])
    )
    reg.register(
        _make_skill("sc_qc", "single-cell-transcriptomics", ["single-cell-transcriptomics"])
    )
    reg.register(
        _make_skill("spatial_data_io", "spatial-transcriptomics", ["spatial-transcriptomics"])
    )
    reg.register(
        _make_skill("spatial_deconv", "spatial-transcriptomics", ["spatial-transcriptomics"])
    )
    reg.register(
        _make_skill(
            "bridge_by_category",
            "bridge",
            [],
            description="Bridge single-cell-transcriptomics to spatial-transcriptomics",
            categories=["bridge"],
        )
    )

    engine = PlanEngine(skill_registry=reg)
    planner = CompositePlanner(plan_engine=engine, skill_registry=reg)
    plan = await planner.plan(cross_domain_intent)

    assert plan is not None
    assert any(p.phase_type == "bridge" for p in plan.phases)
    bridge_phase = next(p for p in plan.phases if p.phase_type == "bridge")
    assert bridge_phase.selected_skill.id == "bridge_by_category"


@pytest.mark.asyncio
async def test_composite_planner_no_bridge_when_none_exists(
    registry_without_bridge, cross_domain_intent, monkeypatch
):
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    engine = PlanEngine(skill_registry=registry_without_bridge)
    planner = CompositePlanner(
        plan_engine=engine,
        skill_registry=registry_without_bridge,
    )
    plan = await planner.plan(cross_domain_intent)

    assert plan is not None
    assert "bridge" not in [p.phase_type for p in plan.phases]


@pytest.mark.asyncio
async def test_composite_planner_returns_none_for_single_domain(
    registry_with_bridge, monkeypatch
):
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    engine = PlanEngine(skill_registry=registry_with_bridge)
    planner = CompositePlanner(
        plan_engine=engine,
        skill_registry=registry_with_bridge,
    )
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
        domain="single-cell-transcriptomics",
    )
    plan = await planner.plan(intent)
    assert plan is None


@pytest.mark.asyncio
async def test_composite_planner_updates_transitions(
    registry_with_bridge, cross_domain_intent, monkeypatch
):
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    engine = PlanEngine(skill_registry=registry_with_bridge)
    planner = CompositePlanner(
        plan_engine=engine,
        skill_registry=registry_with_bridge,
    )
    plan = await planner.plan(cross_domain_intent)

    assert plan is not None
    assert len(plan.phase_transitions) == len(plan.phases) - 1
    bridge_phase = next(p for p in plan.phases if p.phase_type == "bridge")
    assert any(t["to"] == bridge_phase.phase_type for t in plan.phase_transitions)
    assert any(t["from"] == bridge_phase.phase_type for t in plan.phase_transitions)
