"""Trust levels and differentiated permission policies for skills.

Implements the four-tier trust model (official / verified / community /
experimental) from docs/architecture-assessment-and-optimization.md §P3-1.

The legacy ``metadata["trusted"]`` boolean is mapped onto these levels so
existing skills keep their behavior; new skills can additionally declare an
explicit ``trust_level`` in SKILL.md frontmatter. Each level maps to a
:class:`TrustPolicy` that differentiates sandbox backend, HITL requirement,
and CodeAct cache usage.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    """Four-tier skill trust model."""

    OFFICIAL = "official"
    VERIFIED = "verified"
    COMMUNITY = "community"
    EXPERIMENTAL = "experimental"


def resolve_trust_level(skill: Any) -> TrustLevel:
    """Resolve the effective trust level of a skill.

    Precedence:
      1. Explicit ``metadata["trust_level"]`` (frontmatter or API override).
         Invalid values are ignored with a warning.
      2. ``source == "builtin"`` -> OFFICIAL.
      3. trusted and ``source == "community"`` -> COMMUNITY.
      4. trusted -> VERIFIED.
      5. Otherwise -> EXPERIMENTAL.
    """
    metadata = getattr(skill, "metadata", None) or {}

    explicit = metadata.get("trust_level")
    if explicit is not None:
        try:
            return TrustLevel(str(explicit).strip().lower())
        except ValueError:
            logger.warning(
                "Skill '%s' has invalid trust_level %r; ignoring it",
                getattr(skill, "id", "<unknown>"),
                explicit,
            )

    source = metadata.get("source") or "builtin"
    if source == "builtin":
        return TrustLevel.OFFICIAL
    if metadata.get("trusted"):
        if source == "community":
            return TrustLevel.COMMUNITY
        return TrustLevel.VERIFIED
    return TrustLevel.EXPERIMENTAL


@dataclass(frozen=True)
class TrustPolicy:
    """Differentiated permissions for a trust level."""

    level: TrustLevel
    can_execute: bool
    allow_local_sandbox: bool
    require_hitl: bool
    use_code_cache: bool


def policy_for(level: TrustLevel, interactive: Optional[bool] = None) -> TrustPolicy:
    """Return the permission policy for a trust level.

    ``interactive`` defaults to ``settings.interactive_mode``. EXPERIMENTAL
    skills may only execute in interactive mode and always require HITL
    review; in non-interactive mode they are refused, matching the legacy
    untrusted-skill behavior.
    """
    if interactive is None:
        interactive = settings.interactive_mode
    return TrustPolicy(
        level=level,
        can_execute=level is not TrustLevel.EXPERIMENTAL or interactive,
        allow_local_sandbox=level in (TrustLevel.OFFICIAL, TrustLevel.VERIFIED),
        require_hitl=level is TrustLevel.EXPERIMENTAL,
        use_code_cache=level is not TrustLevel.EXPERIMENTAL,
    )
