"""ModeSelector — plan-level execution mode selection.

Selects between three plan-level execution modes:

  - ``fixed_pipeline``: run the plan as-is with curated skills (no LLM
    code generation). Cheapest and most reproducible, but only viable
    when curated skills cover the plan well.
  - ``codeact``: let the agent generate bridging/analysis code (CodeAct).
    Most flexible, but costs LLM tokens and is less deterministic.
  - ``auto``: defer per-task routing to the ``Orchestrator``: tasks are
    dispatched through the supervisor's curated-skill path when a supervisor
    is registered (otherwise the curated skill runtime directly), and
    failures are recovered by the CodeAct fallback. This is the previous
    behaviour and the default.

The selector is intentionally rule-based so its decisions are auditable.

Signals used (all from ``PlanResult``):
  - skill coverage: fraction of phases with a ``selected_skill``
  - gap count: number of ``PlannedGap`` entries with ``gap_type != "none"``
  - ``risk_level``, ``is_fallback``, ``is_information_request``
  - standalone / no-domain phases: phases whose derivation is
    ``standalone-skill`` or ``llm-fallback``

Decision rules (defaults in parentheses, overridable via constructor):
  1. Information-request plans stay ``auto`` (nothing to execute yet).
  2. Fallback plans or plans with no phases -> ``codeact``
     (no curated pipeline exists to fix).
  3. Any standalone / no-domain phase -> ``codeact``
     (curated pipeline cannot cover it).
  4. If historical mode-selection lore exists for this plan's intent
     features and the historical confidence is high enough, use the
     recorded best mode.
  5. coverage >= fixed_pipeline_coverage (0.8)
     AND gap_count <= max_gaps_for_fixed (0)
     AND risk_level != "high"
     -> ``fixed_pipeline``.
  6. coverage < codeact_coverage (0.5)
     OR gap_count >= codeact_gap_count (2)
     -> ``codeact``.
  7. Otherwise -> ``auto`` (middle ground: orchestrator-routed execution).
"""

from typing import List, Optional

from homomics_lab.agent.plan.mode_selection_lore import (
    IntentFeatures,
    ModeSelectionLore,
)
from homomics_lab.agent.plan.models import PlanResult

VALID_EXECUTION_MODES = ("auto", "fixed_pipeline", "codeact")

# Phase derivations that indicate the phase is not part of a curated,
# domain-declared pipeline.
_NON_PIPELINE_DERIVATIONS = ("standalone-skill", "llm-fallback")


class ModeSelector:
    """Rule-based plan-level execution mode selection with learned prior.

    Thresholds can be overridden via constructor arguments, e.g. per
    project configuration.  When ``lore`` is provided (or left as the
    default), historically recorded mode observations are consulted before
    the hard-coded heuristic.
    """

    def __init__(
        self,
        fixed_pipeline_coverage: float = 0.8,
        codeact_coverage: float = 0.5,
        max_gaps_for_fixed: int = 0,
        codeact_gap_count: int = 2,
        lore: Optional[ModeSelectionLore] = None,
        lore_confidence_threshold: float = 0.7,
        lore_min_samples: float = 3.0,
        use_lore: bool = True,
    ):
        if not 0.0 <= codeact_coverage <= fixed_pipeline_coverage <= 1.0:
            raise ValueError(
                "Require 0 <= codeact_coverage <= fixed_pipeline_coverage <= 1"
            )
        self.fixed_pipeline_coverage = fixed_pipeline_coverage
        self.codeact_coverage = codeact_coverage
        self.max_gaps_for_fixed = max_gaps_for_fixed
        self.codeact_gap_count = codeact_gap_count
        self.lore_confidence_threshold = lore_confidence_threshold
        self.lore_min_samples = lore_min_samples
        if lore is not None:
            self.lore = lore
        elif use_lore:
            self.lore = ModeSelectionLore()
        else:
            self.lore = None

    @staticmethod
    def extract_intent_features(plan: PlanResult) -> IntentFeatures:
        """Extract stable, hashable intent features from a plan.

        The features are used as the lookup key for historical mode-selection
        lore.  Domain and intent are recovered from the reproducibility
        context when available, otherwise from the strategy name.
        """
        return IntentFeatures.from_plan(plan)

    def select(self, plan: PlanResult) -> str:
        """Return the execution mode for a plan.

        Always returns one of ``VALID_EXECUTION_MODES``.
        """
        # 1. Information requests are not executable plans; leave routing
        # to the caller.
        if plan.is_information_request:
            return "auto"

        # 2. Fallback / empty plans have no curated pipeline to run.
        if plan.is_fallback or not plan.phases:
            return "codeact"

        has_non_pipeline_phase = any(
            (phase.derivation or "") in _NON_PIPELINE_DERIVATIONS
            for phase in plan.phases
        )

        # 3. Standalone / LLM-fallback phases cannot be served by a fixed
        # curated pipeline.
        if has_non_pipeline_phase:
            return "codeact"

        # 4. Consult historical lore before the heuristic.  The prior only
        # wins when we have enough observations and the winning mode is
        # clearly dominant.
        if self.lore is not None:
            features = self.extract_intent_features(plan)
            recommended, confidence = self.lore.get_recommendation(
                features,
                min_samples=self.lore_min_samples,
                confidence_threshold=self.lore_confidence_threshold,
            )
            if recommended is not None:
                return recommended

        coverage = self._skill_coverage(plan)
        gap_count = self._gap_count(plan)

        # 5. High coverage, few gaps, acceptable risk -> fixed pipeline.
        if (
            coverage >= self.fixed_pipeline_coverage
            and gap_count <= self.max_gaps_for_fixed
            and plan.risk_level != "high"
        ):
            return "fixed_pipeline"

        # 6. Low coverage or many gaps -> codeact.
        if coverage < self.codeact_coverage or gap_count >= self.codeact_gap_count:
            return "codeact"

        # 7. Middle ground: let the Orchestrator route per task (supervisor
        # curated path with CodeAct fallback).
        return "auto"

    @staticmethod
    def _skill_coverage(plan: PlanResult) -> float:
        """Fraction of phases that have a selected skill."""
        if not plan.phases:
            return 0.0
        covered = sum(1 for p in plan.phases if p.selected_skill is not None)
        return covered / len(plan.phases)

    @staticmethod
    def _gap_count(plan: PlanResult) -> int:
        """Number of real (non-"none") gaps in the plan."""
        return len([g for g in plan.gaps if g.gap_type != "none"])

    def explain(self, plan: PlanResult) -> List[str]:
        """Return the signal values behind ``select`` for audit output."""
        lines = [
            f"coverage={self._skill_coverage(plan):.2f}",
            f"gaps={self._gap_count(plan)}",
            f"risk_level={plan.risk_level}",
            f"is_fallback={plan.is_fallback}",
        ]
        if self.lore is not None:
            features = self.extract_intent_features(plan)
            recommended, confidence = self.lore.get_recommendation(
                features,
                min_samples=self.lore_min_samples,
                confidence_threshold=self.lore_confidence_threshold,
            )
            lore_note = (
                f"lore_recommendation={recommended},confidence={confidence:.2f}"
                if recommended is not None
                else f"lore_confidence={confidence:.2f}"
            )
            lines.append(lore_note)
        lines.append(f"selected_mode={self.select(plan)}")
        return lines
