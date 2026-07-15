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

_MAX_INLINE_BYTES = 200_000  # ceiling for inlining a *text* file's content into the prompt

# Binary / large formats that must never be inlined into the prompt. They are
# passed to skills by resolved path instead.
_BINARY_EXTS = frozenset(
    {
        ".h5ad",
        ".h5",
        ".hdf5",
        ".rds",
        ".rdata",
        ".rda",
        ".loom",
        ".zarr",
        ".parquet",
        ".mtx",
        ".npy",
        ".npz",
        ".bam",
        ".cram",
        ".sam",
        ".fastq",
        ".fq",
        ".gz",
        ".zip",
        ".tar",
        ".png",
        ".jpg",
        ".jpeg",
        ".pdf",
        ".tif",
        ".tiff",
    }
)

_SKILL_REF_RE = re.compile(r"@skill:([A-Za-z0-9_\-]+)")
_FILE_REF_RE = re.compile(r"@file:([^\s]+)")


def _resolve_project_file(path: str, project_id: str) -> Path:
    """Resolve a project-relative path against the canonical workspace first.

    Files managed by the project live under ``workspaces/{project_id}/``.
    Legacy uploads via the file API may still reside under ``raw/{project_id}/``,
    so we fall back there if the workspace lookup fails.
    """
    roots = [
        settings.data_dir / "workspaces" / project_id,
        settings.data_dir / "raw" / project_id,
    ]
    last_error: Exception | None = None
    for root in roots:
        try:
            return safe_path(path, root=root.resolve(), must_exist=True)
        except (ValueError, FileNotFoundError) as exc:
            last_error = exc
            continue
    raise FileNotFoundError(
        f"File not found: {path}"
    ) from last_error


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
        for path in file_paths:
            try:
                target = _resolve_project_file(path, project_id)
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
            suffix = target.suffix.lower()
            if size > _MAX_INLINE_BYTES or suffix in _BINARY_EXTS:
                kind = "binary" if suffix in _BINARY_EXTS else "large"
                appendix_parts.append(
                    f"<file path=\"{path}\" resolved=\"{target}\">"
                    f"[{kind} file, {size} bytes; pass the resolved path to the skill, "
                    f"do not inline]</file>"
                )
                continue

            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except UnicodeDecodeError:
                appendix_parts.append(
                    f"<file path=\"{path}\" resolved=\"{target}\">"
                    f"[binary file, {size} bytes; pass the resolved path to the skill, "
                    f"do not inline]</file>"
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
