"""Prompt template registry for HomomicsLab.

Provides centralized, layered prompt management: global templates live in
``templates/base.yaml`` and each ``domain.yaml`` can contribute domain-specific
overrides. Templates are rendered with Jinja2.
"""

from homomics_lab.prompts.loader import (
    initialize_prompt_registry,
    load_base_templates,
    load_domain_prompts,
)
from homomics_lab.prompts.registry import (
    PromptRegistry,
    get_prompt_registry,
    render_prompt,
)

__all__ = [
    "PromptRegistry",
    "get_prompt_registry",
    "render_prompt",
    "initialize_prompt_registry",
    "load_base_templates",
    "load_domain_prompts",
]
