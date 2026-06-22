"""Verify that external skill collections load correctly under the agent-first model."""

from pathlib import Path

import pytest

from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor


@pytest.fixture
def registry_with_external_skills():
    """Registry populated from the canonical skill store if available."""
    registry = SkillRegistry()
    store_root = Path(__file__).parents[3] / "data" / "skill_store" / "imported"
    if not store_root.exists():
        return registry

    loader = SkillLoader(registry=registry)
    for namespace_dir in store_root.iterdir():
        if not namespace_dir.is_dir():
            continue
        for skill_dir in namespace_dir.iterdir():
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
                continue
            try:
                skill = loader.load_discovery(skill_dir)
                skill.metadata.setdefault("source", "external")
                skill.metadata.setdefault("trusted", False)
                registry.register(skill)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"Warning: failed to load discovery skill {skill_dir}: {exc}")
    return registry


@pytest.mark.parametrize(
    "skill_id, expected_runtime_type, expected_has_scripts, expected_has_entrypoint",
    [
        # NanoResearch skills: tool_type python/mixed, scripts with helper functions, no entrypoint
        ("bio-single-cell-doublet-scrublet", "python", True, False),
        # These NanoResearch skills have no scripts/ dir; they are pure documentation/agent skills
        ("bio-single-cell-preprocessing", "mixed", False, False),
        ("bio-single-cell-clustering", "mixed", False, False),
        # paperwriting skills: no tool_type, defaults to python but acts as agent
        ("scientific-manuscript", "python", True, False),
        ("scientific-research-design", "python", False, False),
    ],
)
def test_external_skill_classification(
    registry_with_external_skills,
    skill_id,
    expected_runtime_type,
    expected_has_scripts,
    expected_has_entrypoint,
):
    """Imported external skills are classified according to the agent-first rules."""
    skill = registry_with_external_skills.get(skill_id)
    if skill is None:
        pytest.skip(f"Skill {skill_id} not found in imported skill store")

    assert skill.runtime.type == expected_runtime_type
    assert skill.has_scripts is expected_has_scripts
    assert skill.has_entrypoint is expected_has_entrypoint


@pytest.mark.parametrize(
    "skill_id",
    [
        "bio-single-cell-doublet-scrublet",
        "bio-single-cell-preprocessing",
        "bio-single-cell-clustering",
    ],
)
def test_nanoresearch_python_skills_are_declarative(
    registry_with_external_skills, skill_id
):
    """NanoResearch python skills without entrypoints should route to agent/knowledge."""
    skill = registry_with_external_skills.get(skill_id)
    if skill is None:
        pytest.skip(f"Skill {skill_id} not found in imported skill store")

    assert SkillRuntimeExecutor._is_declarative(skill) is True


def test_doublet_scrublet_body_loaded_on_activation(registry_with_external_skills):
    """Activating a discovery-level skill lazily loads its body."""
    skill = registry_with_external_skills.get("bio-single-cell-doublet-scrublet")
    if skill is None:
        pytest.skip("bio-single-cell-doublet-scrublet not found")

    assert skill.metadata.get("disclosure_level") == "discovery"
    assert skill.metadata.get("instructions") == ""

    activated = registry_with_external_skills.activate("bio-single-cell-doublet-scrublet")
    assert activated is not None
    assert activated.metadata.get("disclosure_level") == "activated"
    assert activated.metadata.get("instructions") != ""
