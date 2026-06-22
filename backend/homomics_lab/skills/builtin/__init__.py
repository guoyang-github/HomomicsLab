"""Builtin skills loaded from directory structure.

All builtin skills now follow the same directory layout as external skills:
  builtin/<skill-name>/
    SKILL.md
    [optional] scripts/
    [optional] references/
    [optional] assets/

Builtin skills are registered at the DISCOVERY level (name + description only)
and lazily activated on first execution, following OpenClaw-style progressive
disclosure.
"""

from pathlib import Path

from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.loader import SkillLoader

_BUILTIN_DIR = Path(__file__).parent


def _register_skill_dir(
    executor: SkillRuntimeExecutor,
    skill_dir: Path,
    source: str,
) -> None:
    """Register a single skill directory at discovery level."""
    loader = SkillLoader(executor.registry)
    skill = loader.load_discovery(skill_dir)
    # Use directory name as canonical skill ID (underscores, no hyphens)
    skill.id = skill_dir.name
    skill.metadata["source"] = source
    skill.metadata["namespace"] = source
    skill.metadata["trusted"] = source == "builtin"
    executor.registry.register(skill)


def register_builtin_skills(executor: SkillRuntimeExecutor) -> None:
    """Register builtin skills at discovery level.

    Builtin skills use the same format as external skills (SKILL.md + optional
    resources). Legacy business skills have been removed; domain-specific
    capabilities should come from external skill collections.
    """
    # Agent meta-capability builtin skills
    for skill_dir in _BUILTIN_DIR.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            _register_skill_dir(executor, skill_dir, source="builtin")
