"""Canonical routing decision for user intents.

HomomicsLab has several planners (standalone skill, domain template, open agent,
cross-domain composition) and a few hard-coded fast paths (file conversion, QA,
clarification).  ``RoutingDecision`` is the single value object that records
which path was chosen, why it was chosen, and what data the path needs.

All routing logic—legacy rule-based, capability-first, or future ML-based—should
produce a ``RoutingDecision``.  ``TaskDecomposer`` then dispatches on
``decision.route`` without re-evaluating intent features.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.skills.models import SkillDefinition


class Route(str, Enum):
    """Canonical execution route for an intent."""

    CLARIFICATION = "clarification"
    FILE_CONVERSION = "file_conversion"
    QA = "qa"
    DIRECT_RESPONSE = "direct_response"
    STANDALONE_SKILL = "standalone_skill"
    DOMAIN_TEMPLATE = "domain_template"
    CROSS_DOMAIN = "cross_domain"
    OPEN_AGENT = "open_agent"
    FALLBACK_SUGGESTION = "fallback_suggestion"


@dataclass
class RoutingDecision:
    """Canonical routing decision produced for a user intent."""

    route: Route
    reason: str = ""
    confidence: float = 0.0

    # Domain/template context
    domains: List[str] = field(default_factory=list)
    template: Optional[AnalysisTemplate] = None

    # Skill context (pre-resolved skills to avoid double retrieval)
    skills: List[SkillDefinition] = field(default_factory=list)

    # Open-agent / fallback context
    data_state: Optional[DataState] = None
    suggestion_text: Optional[str] = None

    # Audit trail: every considered alternative with its score/reason.
    # This is the foundation for routing observability and HITL explanations.
    trace: List[Dict[str, Any]] = field(default_factory=list)

    def with_trace_entry(self, route: Route, reason: str, score: float = 0.0) -> "RoutingDecision":
        """Return a new decision with an additional trace entry."""
        new_trace = list(self.trace)
        new_trace.append({"route": route.value, "reason": reason, "score": score})
        return RoutingDecision(
            route=self.route,
            reason=self.reason,
            confidence=self.confidence,
            domains=list(self.domains),
            template=self.template,
            skills=list(self.skills),
            data_state=self.data_state,
            suggestion_text=self.suggestion_text,
            trace=new_trace,
        )

    @classmethod
    def direct(cls, route: Route, reason: str) -> "RoutingDecision":
        """Factory for routes that need no extra context (clarification/QA/file)."""
        return cls(route=route, reason=reason, confidence=1.0)
