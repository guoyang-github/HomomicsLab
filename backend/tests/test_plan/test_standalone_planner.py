"""Tests for the standalone skill planner."""

import pytest

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.standalone_planner import StandaloneSkillPlanner
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


def _make_skill(
    skill_id: str,
    name: str,
    description: str,
    domains: list = None,
    categories: list = None,
) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=name,
        version="1.0.0",
        category=(categories[0] if categories else "general"),
        description=description,
        domains=domains or [],
        categories=categories or [],
    )


@pytest.fixture
def registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(
        _make_skill(
            "file_converter",
            "File Converter",
            "Convert files between formats",
            categories=["utility"],
        )
    )
    reg.register(
        _make_skill(
            "text_summarizer",
            "Text Summarizer",
            "Summarize long text passages",
            categories=["nlp"],
        )
    )
    reg.register(
        _make_skill(
            "bio_qa",
            "Biology QA",
            "Answer biology questions",
            domains=["biology"],
            categories=["qa"],
        )
    )
    return reg


def test_standalone_planner_returns_plan_for_matching_skill(registry):
    planner = StandaloneSkillPlanner(skill_registry=registry, top_k=3)
    intent = UserIntent(
        intent_type="general", interaction_mode="execute", scope="single_step", original_message="summarize this article",
    )

    plan = planner.plan(intent)

    assert plan is not None
    assert plan.derivation == "standalone-skill"
    assert plan.risk_level == "low"
    assert not plan.approval_required
    assert len(plan.phases) == 1
    assert plan.phases[0].selected_skill.id == "text_summarizer"
    assert plan.phases[0].derivation == "standalone-skill"


def test_standalone_planner_ignores_domain_skills(registry):
    planner = StandaloneSkillPlanner(skill_registry=registry, top_k=3)
    intent = UserIntent(
        intent_type="general", interaction_mode="execute", scope="single_step", original_message="biology question",
    )

    plan = planner.plan(intent)

    # "bio_qa" belongs to a domain, so it must not be selected.
    assert plan is None or all(
        p.selected_skill.id != "bio_qa" for p in plan.phases
    )


def test_standalone_planner_returns_none_when_no_match(registry):
    planner = StandaloneSkillPlanner(skill_registry=registry, top_k=3)
    intent = UserIntent(
        intent_type="general", interaction_mode="execute", scope="single_step", original_message="xyz nonexistent thing",
    )

    plan = planner.plan(intent)

    assert plan is None


def test_standalone_planner_respects_top_k():
    reg = SkillRegistry()
    for i in range(5):
        reg.register(
            _make_skill(
                f"skill_{i}",
                f"Skill {i}",
                f"Description for skill {i}",
                categories=["general"],
            )
        )
    planner = StandaloneSkillPlanner(skill_registry=reg, top_k=2)
    intent = UserIntent(
        intent_type="general", interaction_mode="execute", scope="single_step", original_message="skill",
    )

    plan = planner.plan(intent)

    assert plan is not None
    assert len(plan.phases) <= 2
