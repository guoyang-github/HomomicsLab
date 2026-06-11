"""Builtin skills loaded from directory structure.

All builtin skills now follow the same directory layout as external skills:
  builtin/<skill-name>/
    SKILL.md
    scripts/python/
      run.py
"""

from pathlib import Path

from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.loader import SkillLoader

_BUILTIN_DIR = Path(__file__).parent


def register_builtin_skills(executor: SkillRuntimeExecutor) -> None:
    """Register builtin skills from directory structure.

    Builtin skills now use the same format as external skills (SKILL.md + scripts/),
    eliminating the distinction between builtin (code strings) and external (file-based).
    """
    loader = SkillLoader(executor.registry)

    # Discover all builtin skill directories
    for skill_dir in _BUILTIN_DIR.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            skill = loader.load_skill(skill_dir)
            # Use directory name as canonical skill ID (underscores, no hyphens)
            skill.id = skill_dir.name
            # Mark source as builtin
            skill.metadata["source"] = "builtin"
            executor.registry.register(skill)
