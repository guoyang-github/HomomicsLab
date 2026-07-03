"""Load prompt templates from YAML files and domain declarations."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from homomics_lab.prompts.registry import PromptRegistry, get_prompt_registry


BASE_TEMPLATES_PATH = Path(__file__).parent / "templates" / "base.yaml"


def _flatten_prompts(
    prompts: Dict[str, Any],
    prefix: str = "",
    domain: Optional[str] = None,
    registry: Optional[PromptRegistry] = None,
) -> None:
    """Recursively flatten a nested prompt dict into dotted names.

    Example:
        {"system": {"base": "...", "qa": "..."}}
    becomes:
        register("system.base", "...")
        register("system.qa", "...")
    """
    reg = registry or get_prompt_registry()
    for key, value in prompts.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _flatten_prompts(value, prefix=name, domain=domain, registry=reg)
        elif isinstance(value, str):
            reg.register(name, value.strip(), domain=domain)
        else:
            # Non-string values are ignored; prompts must be strings.
            continue


def load_base_templates(registry: Optional[PromptRegistry] = None) -> None:
    """Load global prompt templates from ``templates/base.yaml``."""
    reg = registry or get_prompt_registry()
    if not BASE_TEMPLATES_PATH.exists():
        return

    with open(BASE_TEMPLATES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if "prompts" in data:
        _flatten_prompts(data["prompts"], domain=None, registry=reg)


def load_domain_prompts(
    domain: str,
    prompts: Dict[str, Any],
    registry: Optional[PromptRegistry] = None,
) -> None:
    """Load prompt overrides declared inside a ``domain.yaml``."""
    reg = registry or get_prompt_registry()
    reg.clear_domain(domain)
    _flatten_prompts(prompts, domain=domain, registry=reg)


def initialize_prompt_registry(registry: Optional[PromptRegistry] = None) -> PromptRegistry:
    """Load base templates and return the registry."""
    reg = registry or get_prompt_registry()
    load_base_templates(reg)
    return reg
