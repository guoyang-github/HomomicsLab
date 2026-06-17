"""Resolve @-references in user chat messages.

Supported syntax:
  @skill:<skill-id>  – injects a concise skill description.
  @file:<path>       – injects the content of a project file.
"""

import re
from pathlib import Path
from typing import Optional

from homomics_lab.config import settings
from homomics_lab.security import safe_path, validate_project_id
from homomics_lab.skills.runtime import SkillRuntimeExecutor

_MAX_FILE_BYTES = 200_000  # ~50k tokens ceiling for a single file reference

_SKILL_REF_RE = re.compile(r"@skill:([A-Za-z0-9_\-]+)")
_FILE_REF_RE = re.compile(r"@file:([^\s]+)")


def _project_root(project_id: str) -> Path:
    return (settings.data_dir / "raw" / project_id).resolve()


def _describe_skill(skill) -> str:
    lines = [
        f"<skill id=\"{skill.id}\">",
        f"Name: {skill.name}",
        f"Category: {skill.category}",
        f"Runtime: {skill.runtime.type}",
    ]
    if skill.description:
        lines.append(f"Description: {skill.description}")
    if skill.runtime.dependencies:
        lines.append(f"Dependencies: {', '.join(skill.runtime.dependencies)}")
    keywords = skill.metadata.get("keywords", [])
    if keywords:
        lines.append(f"Keywords: {', '.join(keywords)}")
    lines.append("</skill>")
    return "\n".join(lines)


async def resolve_chat_references(
    message: str,
    project_id: str,
    skill_executor: Optional[SkillRuntimeExecutor] = None,
) -> str:
    """Expand any @skill: and @file: references found in *message*.

    The original message is preserved; resolved context is appended as a
    system-style appendix so the agent can see the referenced content.
    """
    try:
        project_id = validate_project_id(project_id)
    except ValueError:
        project_id = "default"

    appendix_parts: list[str] = []

    skill_ids = set(_SKILL_REF_RE.findall(message))
    if skill_ids and skill_executor is not None:
        for skill_id in skill_ids:
            skill = skill_executor.registry.get(skill_id)
            if skill is None:
                appendix_parts.append(
                    f"<skill id=\"{skill_id}\">[Skill not found]</skill>"
                )
                continue
            appendix_parts.append(_describe_skill(skill))

    file_paths = set(_FILE_REF_RE.findall(message))
    if file_paths:
        root = _project_root(project_id)
        for path in file_paths:
            try:
                target = safe_path(path, root=root, must_exist=True)
            except (ValueError, FileNotFoundError) as exc:
                appendix_parts.append(
                    f"<file path=\"{path}\">[File not accessible: {exc}]</file>"
                )
                continue

            if not target.is_file():
                appendix_parts.append(
                    f"<file path=\"{path}\">[Path is not a file]</file>"
                )
                continue

            size = target.stat().st_size
            if size > _MAX_FILE_BYTES:
                appendix_parts.append(
                    f"<file path=\"{path}\">[File too large: {size} bytes; limit is {_MAX_FILE_BYTES}]</file>"
                )
                continue

            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except UnicodeDecodeError:
                appendix_parts.append(
                    f"<file path=\"{path}\">[Binary file, content not shown]</file>"
                )
                continue

            appendix_parts.append(
                f"<file path=\"{path}\">\n{content}\n</file>"
            )

    if not appendix_parts:
        return message

    appendix = "\n\n".join(
        ["---", "Referenced context:"] + appendix_parts
    )
    return f"{message}\n\n{appendix}"
