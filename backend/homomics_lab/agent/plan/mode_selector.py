"""ModeSelector — plan-level execution mode selection.

Selects between three plan-level execution modes:

  - ``fixed_pipeline``: run the plan as-is with curated skills (no LLM
    code generation). Cheapest and most reproducible, but only viable
    when curated skills cover the plan well.
  - ``codeact``: let the agent generate bridging/analysis code (CodeAct).
    Most flexible, but costs LLM tokens and is less deterministic.
  - ``auto``: defer to the phase-level ``ExecutionRouter``
    (``agent/execution_router.py``), which decides per phase. This is the
    previous behaviour and the default.

The selector is intentionally rule-based so its decisions are auditable,
mirroring the design philosophy of ``ExecutionRouter``.

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
  4. coverage >= fixed_pipeline_coverage (0.8)
     AND gap_count <= max_gaps_for_fixed (0)
     AND risk_level != "high"
     -> ``fixed_pipeline``.
  5. coverage < codeact_coverage (0.5)
     OR gap_count >= codeact_gap_count (2)
     -> ``codeact``.
  6. Otherwise -> ``auto`` (middle ground: per-phase routing).
"""

from typing import List

from homomics_lab.agent.plan.models import PlanResult

VALID_EXECUTION_MODES = ("auto", "fixed_pipeline", "codeact")

# Phase derivations that indicate the phase is not part of a curated,
# domain-declared pipeline.
_NON_PIPELINE_DERIVATIONS = ("standalone-skill", "llm-fallback")


class ModeSelector:
    """Rule-based plan-level execution mode selection.

    Thresholds can be overridden via constructor arguments, e.g. per
    project configuration.
    """

    def __init__(
        self,
        fixed_pipeline_coverage: float = 0.8,
        codeact_coverage: float = 0.5,
        max_gaps_for_fixed: int = 0,
        codeact_gap_count: int = 2,
    ):
        if not 0.0 <= codeact_coverage <= fixed_pipeline_coverage <= 1.0:
            raise ValueError(
                "Require 0 <= codeact_coverage <= fixed_pipeline_coverage <= 1"
            )
        self.fixed_pipeline_coverage = fixed_pipeline_coverage
        self.codeact_coverage = codeact_coverage
        self.max_gaps_for_fixed = max_gaps_for_fixed
        self.codeact_gap_count = codeact_gap_count

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

        coverage = self._skill_coverage(plan)
        gap_count = self._gap_count(plan)
        has_non_pipeline_phase = any(
            (phase.derivation or "") in _NON_PIPELINE_DERIVATIONS
            for phase in plan.phases
        )

        # 3. Standalone / LLM-fallback phases cannot be served by a fixed
        # curated pipeline.
        if has_non_pipeline_phase:
            return "codeact"

        # 4. High coverage, few gaps, acceptable risk -> fixed pipeline.
        if (
            coverage >= self.fixed_pipeline_coverage
            and gap_count <= self.max_gaps_for_fixed
            and plan.risk_level != "high"
        ):
            return "fixed_pipeline"

        # 5. Low coverage or many gaps -> codeact.
        if coverage < self.codeact_coverage or gap_count >= self.codeact_gap_count:
            return "codeact"

        # 6. Middle ground: let the phase-level ExecutionRouter decide.
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
        return [
            f"coverage={self._skill_coverage(plan):.2f}",
            f"gaps={self._gap_count(plan)}",
            f"risk_level={plan.risk_level}",
            f"is_fallback={plan.is_fallback}",
            f"selected_mode={self.select(plan)}",
        ]
