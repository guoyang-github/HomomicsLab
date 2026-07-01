"""Tests for LLMFallbackPlanner deterministic fallback."""

import pytest

from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.agent.plan.llm_fallback import LLMFallbackPlanner
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def planner_with_skills():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="Quality control",
            version="1.0",
            category="single-cell",
            description="Filter low-quality cells.",
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_normalize",
            name="Normalize",
            version="1.0",
            category="single-cell",
            description="Normalize counts.",
        )
    )
    reg.register(
        SkillDefinition(
            id="general_plot",
            name="Plot",
            version="1.0",
            category="visualization",
            description="Make plots.",
        )
    )
    return LLMFallbackPlanner(skill_registry=reg, llm_client=None, deterministic_fallback=True)


@pytest.mark.asyncio
async def test_deterministic_fallback_without_llm(planner_with_skills):
    """When LLM is unavailable, planner still builds executable phases from skills."""
    intent = UserIntent(
        analysis_type="generic_analysis",
        complexity="complex",
        original_message="quality control and normalize my single-cell data",
    )
    plan = await planner_with_skills.generate_plan(intent)

    assert plan.strategy_name == "llm_fallback"
    assert len(plan.phases) > 0
    ids = {p.selected_skill.id for p in plan.phases if p.selected_skill}
    assert "scanpy_qc" in ids
