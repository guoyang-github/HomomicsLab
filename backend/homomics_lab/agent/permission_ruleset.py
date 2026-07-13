"""Per-agent / per-domain permission rulesets.

Permission rules reduce approval fatigue by declaring which tools and skills can
be executed without a HITL pause for a given role/domain combination.  Deny lists
still override everything, and a maximum auto-approve risk level prevents
high-risk calls from silently bypassing the user.
"""

from __future__ import annotations

import json
import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from homomics_lab.config import settings
from homomics_lab.domain.registry import get_domain_registry

logger = logging.getLogger(__name__)

RISK_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

DEFAULT_RULESET_PATH = "permission_rulesets.json"


def _risk_lte(a: Optional[str], b: Optional[str]) -> bool:
    """Return True when risk ``a`` is no more severe than ``b``."""
    return RISK_ORDER.get(a or "low", 0) <= RISK_ORDER.get(b or "low", 0)


def _matches(value: str, patterns: List[str]) -> bool:
    """Return True when ``value`` matches any exact or glob pattern."""
    value_lower = value.lower()
    for pattern in patterns:
        pat_lower = pattern.lower()
        if value_lower == pat_lower or fnmatch(value_lower, pat_lower):
            return True
    return False


class PermissionRuleSet(BaseModel):
    """A single ruleset scoped to a role, a domain, or both."""

    role_id: Optional[str] = None
    domain: Optional[str] = None
    auto_approved_tools: List[str] = Field(default_factory=list)
    auto_approved_skills: List[str] = Field(default_factory=list)
    denied_tools: List[str] = Field(default_factory=list)
    denied_skills: List[str] = Field(default_factory=list)
    max_auto_approve_risk_level: str = "low"


class PermissionRegistry:
    """Merged registry of permission rules from domain declarations and disk."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = data_dir or settings.data_dir
        self._rules: List[PermissionRuleSet] = []
        self._load()

    def _rules_path(self) -> Path:
        return self._data_dir / DEFAULT_RULESET_PATH

    def _load(self) -> None:
        self._rules = []
        self._load_from_domains()
        self._load_from_disk()

    def _load_from_domains(self) -> None:
        """Parse ``permissions`` blocks from every loaded domain role."""
        try:
            registry = get_domain_registry()
        except Exception as exc:
            logger.debug("Domain registry not available for permission loading: %s", exc)
            return

        for domain in registry.list_all():
            for role in domain.roles:
                perms = role.permissions
                if not isinstance(perms, dict):
                    continue
                # Only create a ruleset if permission-related keys are present.
                relevant_keys = {
                    "auto_approved_tools",
                    "auto_approved_skills",
                    "denied_tools",
                    "denied_skills",
                    "max_auto_approve_risk_level",
                }
                if not relevant_keys.intersection(perms.keys()):
                    continue
                try:
                    rule = PermissionRuleSet(
                        role_id=role.role_id,
                        domain=domain.domain,
                        auto_approved_tools=perms.get("auto_approved_tools", []),
                        auto_approved_skills=perms.get("auto_approved_skills", []),
                        denied_tools=perms.get("denied_tools", []),
                        denied_skills=perms.get("denied_skills", []),
                        max_auto_approve_risk_level=perms.get(
                            "max_auto_approve_risk_level", "low"
                        ),
                    )
                    self._rules.append(rule)
                except Exception as exc:
                    logger.warning(
                        "Failed to parse permission rules for role %s in domain %s: %s",
                        role.role_id,
                        domain.domain,
                        exc,
                    )

    def _load_from_disk(self) -> None:
        """Load additional rulesets from ``permission_rulesets.json``."""
        path = self._rules_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                logger.warning("Permission rulesets file is not a list; ignoring")
                return
            for item in data:
                try:
                    self._rules.append(PermissionRuleSet(**item))
                except Exception as exc:
                    logger.warning("Failed to parse permission ruleset entry: %s", exc)
        except Exception as exc:
            logger.warning("Failed to load permission rulesets: %s", exc)

    def _matching_rules(
        self,
        role_id: Optional[str],
        domain: Optional[str],
    ) -> List[PermissionRuleSet]:
        """Return rules whose scope covers the requested role/domain."""
        matches: List[PermissionRuleSet] = []
        for rule in self._rules:
            role_match = rule.role_id is None or rule.role_id == role_id
            domain_match = rule.domain is None or rule.domain == domain
            if role_match and domain_match:
                matches.append(rule)
        return matches

    def can_auto_approve_tool(
        self,
        role_id: Optional[str],
        domain: Optional[str],
        tool_name: str,
        risk_level: Optional[str] = None,
    ) -> bool:
        """Return True when ``tool_name`` may run without explicit HITL approval."""
        if self.is_denied_tool(role_id, domain, tool_name):
            return False
        for rule in self._matching_rules(role_id, domain):
            if not rule.auto_approved_tools:
                continue
            if _matches(tool_name, rule.auto_approved_tools):
                if _risk_lte(risk_level or "low", rule.max_auto_approve_risk_level):
                    return True
        return False

    def can_auto_approve_skill(
        self,
        role_id: Optional[str],
        domain: Optional[str],
        skill_id: str,
        risk_level: Optional[str] = None,
    ) -> bool:
        """Return True when ``skill_id`` may run without explicit HITL approval."""
        if self.is_denied_skill(role_id, domain, skill_id):
            return False
        for rule in self._matching_rules(role_id, domain):
            if not rule.auto_approved_skills:
                continue
            if _matches(skill_id, rule.auto_approved_skills):
                if _risk_lte(risk_level or "low", rule.max_auto_approve_risk_level):
                    return True
        return False

    def is_denied_tool(
        self,
        role_id: Optional[str],
        domain: Optional[str],
        tool_name: str,
    ) -> bool:
        """Return True when any matching rule explicitly denies the tool."""
        for rule in self._matching_rules(role_id, domain):
            if rule.denied_tools and _matches(tool_name, rule.denied_tools):
                return True
        return False

    def is_denied_skill(
        self,
        role_id: Optional[str],
        domain: Optional[str],
        skill_id: str,
    ) -> bool:
        """Return True when any matching rule explicitly denies the skill."""
        for rule in self._matching_rules(role_id, domain):
            if rule.denied_skills and _matches(skill_id, rule.denied_skills):
                return True
        return False

    def list_rules(self) -> List[PermissionRuleSet]:
        """Return all loaded rulesets."""
        return list(self._rules)

    def reload(self) -> None:
        """Reload rules from domain declarations and disk."""
        self._load()


def get_permission_registry() -> PermissionRegistry:
    """Return the global permission registry singleton."""
    return PermissionRegistry()
