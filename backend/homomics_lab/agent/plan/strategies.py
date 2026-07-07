"""Analysis strategy templates — domain knowledge for plan generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.config import settings


@dataclass
class StateCheck:
    """A conditional check on data state that may modify the plan."""

    condition: Callable[[DataState], bool]
    action: str  # "insert" | "skip" | "modify_param"
    target: str  # phase_type or param name
    value: Any = None  # new phase or param value
    after: Optional[str] = None  # for insert: phase to insert after


@dataclass
class AnalysisStrategy:
    """A reusable analysis strategy (domain knowledge template).

    Strategies define the standard skeleton for a type of analysis.
    The PlanEngine adapts the skeleton based on the current DataState.
    """

    name: str
    description: str
    applicable_intents: List[str]  # intent patterns this strategy matches
    skeleton: List[Phase]
    state_checks: List[StateCheck] = field(default_factory=list)
    preferred_libraries: Dict[str, List[str]] = field(default_factory=dict)
    code_templates: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    data_sources: List[Dict[str, Any]] = field(default_factory=list)
    fallback_rules: List[Dict[str, str]] = field(default_factory=list)
    phase_transitions: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self):
        self._last_triggered_state_checks: List[Dict[str, Any]] = []

    def generate_skeleton(self, data_state: DataState) -> List[Phase]:
        """Generate the base skeleton, applying state-based modifications."""
        self._last_triggered_state_checks = []
        phases = [
            Phase(
                phase_type=p.phase_type,
                required=p.required,
                description=p.description,
                candidate_skills=list(p.candidate_skills),
                default_skill=p.default_skill,
            )
            for p in self.skeleton
        ]

        for check in self.state_checks:
            if check.condition(data_state):
                self._last_triggered_state_checks.append(
                    {
                        "action": check.action,
                        "target": check.target,
                        "value": check.value,
                        "after": check.after,
                    }
                )
                if check.action == "insert":
                    self._insert_phase(phases, check)
                elif check.action == "skip":
                    self._skip_phase(phases, check.target)
                elif check.action == "modify_param":
                    self._modify_param(phases, check)

        return phases

    def last_triggered_state_checks(self) -> List[Dict[str, Any]]:
        """Return the state checks that fired during the last skeleton generation."""
        return list(self._last_triggered_state_checks)

    @staticmethod
    def _insert_phase(phases: List[Phase], check: StateCheck) -> None:
        """Insert a new phase after a specific phase type."""
        new_phase = Phase(phase_type=check.target, required=True)
        for i, phase in enumerate(phases):
            if phase.phase_type == check.after:
                phases.insert(i + 1, new_phase)
                return
        # If anchor not found, append
        phases.append(new_phase)

    @staticmethod
    def _skip_phase(phases: List[Phase], phase_type: str) -> None:
        """Mark a phase as skipped."""
        for phase in phases:
            if phase.phase_type == phase_type:
                phase.required = False

    @staticmethod
    def _modify_param(phases: List[Phase], check: StateCheck) -> None:
        """Modify parameters of a specific phase."""
        for phase in phases:
            if phase.phase_type == check.target:
                phase.parameters[check.target] = check.value

    def score(self, intent_analysis_type: str, data_state: DataState) -> float:
        """Score how well this strategy matches an intent and data state.

        Scoring rules:
          - Base score 1.0 if the intent is explicitly applicable.
          - +0.2 for each keyword overlap between the intent and the
            strategy's name, description, or skeleton phase types.
          - +0.1 for each skeleton phase type that already has a matching
            key in the data state.
        """
        score = 0.0
        if intent_analysis_type in self.applicable_intents:
            score = 1.0

        intent_tokens = set(intent_analysis_type.lower().replace("_", " ").split())

        # Build a text corpus from strategy metadata and skeleton.
        text_parts = [self.name, self.description]
        for phase in self.skeleton:
            text_parts.append(phase.phase_type)
            if phase.description:
                text_parts.append(phase.description)
        corpus = " ".join(text_parts).lower()
        corpus_tokens = set(corpus.split())

        keyword_hits = sum(1 for token in intent_tokens if token in corpus_tokens and len(token) > 1)
        score += 0.2 * keyword_hits

        # Boost if data state already contains keys matching skeleton phases.
        state_keys = set(data_state.to_dict().keys())
        for ns_values in data_state.domain_state.values():
            if isinstance(ns_values, dict):
                state_keys.update(ns_values.keys())
        phase_types = {phase.phase_type for phase in self.skeleton}
        data_hits = len(phase_types & state_keys)
        score += 0.1 * data_hits

        return score


class StrategyLibrary:
    """Library of built-in analysis strategies."""

    def __init__(self, skill_registry: Optional[Any] = None):
        self._strategies: Dict[str, AnalysisStrategy] = {}
        self._skill_registry = skill_registry
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default strategies.

        Domain declarations take precedence over the generic fallback when
        ``settings.auto_load_domain_strategies`` is enabled. The generic
        strategy is always registered as the ultimate fallback for unknown
        intents.
        """
        # 1. Load domain strategies first so they take priority (when enabled).
        if settings.auto_load_domain_strategies:
            self._load_domain_strategies()

        # 2. Always register the generic fallback.
        if "generic" not in self._strategies:
            self.register(GENERIC_ANALYSIS)

    def _load_domain_strategies(self) -> None:
        """Load strategies from domain.yaml declarations.

        Scans the domains/ directory for domain.yaml files and registers
        their strategies automatically.
        """
        from pathlib import Path
        from homomics_lab.domain.loader import DomainLoader
        from homomics_lab.skills.registry import get_default_registry

        domains_dir = Path(__file__).parent.parent.parent / "domains"
        if not domains_dir.exists():
            return

        skill_registry = self._skill_registry or get_default_registry()
        domain_loader = DomainLoader(skill_registry, self)

        for domain_yaml in domains_dir.rglob("domain.yaml"):
            try:
                domain_loader.load(domain_yaml)
            except Exception:
                # Silently skip invalid domains during default loading
                pass

    def register(self, strategy: AnalysisStrategy) -> None:
        self._strategies[strategy.name] = strategy

    def select(
        self,
        intent_analysis_type: str,
        data_state: Optional[DataState] = None,
        top_k: int = 1,
    ) -> Union[AnalysisStrategy, List[Tuple[AnalysisStrategy, float]]]:
        """Select the best strategy for a given intent type.

        Backward compatibility: when called with the legacy single-argument
        signature (or ``top_k=1``), returns the top strategy directly.
        When ``top_k > 1`` returns a list of ``(strategy, score)`` tuples
        sorted by descending score.
        """
        if data_state is None:
            data_state = DataState()
        ranked = self.select_top_k(intent_analysis_type, data_state, top_k=top_k)
        if top_k == 1:
            return ranked[0][0] if ranked else GENERIC_ANALYSIS
        return ranked

    def select_top_k(
        self,
        intent_analysis_type: str,
        data_state: DataState,
        top_k: int = 3,
    ) -> List[Tuple[AnalysisStrategy, float]]:
        """Return the top-k strategies with scores for a given intent."""
        scored = [
            (strategy, strategy.score(intent_analysis_type, data_state))
            for strategy in self._strategies.values()
        ]
        scored.sort(key=lambda item: item[1], reverse=True)

        # Preserve original fallback behavior: if no strategy explicitly claims
        # this intent (score >= 1.0), promote the generic strategy.
        if scored and scored[0][1] < 1.0:
            generic = self.get("generic") or GENERIC_ANALYSIS
            scored = [(generic, 0.5)] + [
                (s, score) for s, score in scored if s.name != generic.name
            ]

        return scored[:top_k]

    def get(self, name: str) -> Optional[AnalysisStrategy]:
        return self._strategies.get(name)

    def list_all(self) -> List[AnalysisStrategy]:
        return list(self._strategies.values())


# ─────────────────────────────────────────
# Generic fallback strategy
# ─────────────────────────────────────────

GENERIC_ANALYSIS = AnalysisStrategy(
    name="generic",
    description="Generic flexible analysis",
    applicable_intents=["general", "analysis"],
    skeleton=[
        Phase(phase_type="data_loading", required=True),
        Phase(phase_type="exploratory", required=False),
        Phase(phase_type="analysis", required=False),
        Phase(phase_type="visualization", required=False),
    ],
    state_checks=[],
)
