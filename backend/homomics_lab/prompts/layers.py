"""Dual-layer prompt architecture.

Prompts are composed from independent layers rather than a single monolithic
system prompt.  This lets the system keep provider identity, agent persona, and
task instructions separate and reusable.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from homomics_lab.prompts import render_prompt


class PromptLayer(str, Enum):
    """Known prompt layer namespaces."""

    PROVIDER = "provider"
    AGENT = "agent"
    TASK = "task"


def build_system_prompt(
    layers: List[str],
    domain: Optional[str] = None,
    mode: Optional[str] = None,
    task: Optional[str] = None,
) -> str:
    """Render and concatenate prompt layers.

    Layer strings may contain ``{mode}`` or ``{task}`` placeholders, which are
    filled from the corresponding arguments.  Each resolved key is looked up in
    the prompt registry (with domain override support) and rendered.

    Example:
        build_system_prompt(
            ["provider.base", "agent.{mode}", "task.{task}"],
            mode="analysis",
            task="clustering",
        )
    """
    parts: List[str] = []
    for layer in layers:
        key = layer.format(mode=mode or "default", task=task or "default")
        rendered = render_prompt(key, domain=domain, combine=True)
        if rendered:
            parts.append(rendered.strip())
    return "\n\n".join(parts)


def build_task_prompt(
    mode: str,
    task: str,
    domain: Optional[str] = None,
) -> str:
    """Build the full prompt for a task-aware agent turn."""
    return build_system_prompt(
        ["provider.base", "agent.{mode}", "task.{task}"],
        domain=domain,
        mode=mode,
        task=task,
    )
