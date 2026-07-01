"""Plan quality evaluation and historical feedback scoring."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.agent.plan.models import PlanResult
from homomics_lab.agent.plan.validator import PlanValidator
from homomics_lab.knowledge.cbkb import CBKB


@dataclass
class PlanQualityReport:
    """Quality score and findings for a generated plan."""

    score: float  # 0.0 - 1.0
    valid: bool
    findings: List[Dict[str, Any]] = field(default_factory=list)
    strategy_success_rate: float = -1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "valid": self.valid,
            "findings": self.findings,
            "strategy_success_rate": self.strategy_success_rate,
        }


class PlanQualityEvaluator:
    """Evaluate plan quality using validation rules and historical CBKB outcomes."""

    def __init__(
        self,
        plan_validator: PlanValidator,
        cbkb: Optional[CBKB] = None,
    ):
        self.plan_validator = plan_validator
        self.cbkb = cbkb

    def evaluate(
        self,
        plan: PlanResult,
        template_id: Optional[str] = None,
    ) -> PlanQualityReport:
        """Return a quality report for a plan."""
        validation = self.plan_validator.validate(plan)

        findings: List[Dict[str, Any]] = []
        for issue in validation.errors:
            findings.append(
                {
                    "severity": "error",
                    "phase": issue.phase,
                    "skill_id": issue.skill_id,
                    "message": issue.message,
                }
            )
        for issue in validation.warnings:
            findings.append(
                {
                    "severity": "warning",
                    "phase": issue.phase,
                    "skill_id": issue.skill_id,
                    "message": issue.message,
                }
            )

        # Score starts at 1.0 and is penalized for issues.
        score = 1.0
        score -= len(validation.errors) * 0.25
        score -= len(validation.warnings) * 0.05

        # Penalize phases without selected skills.
        unresolved = [p for p in plan.phases if p.selected_skill is None]
        score -= len(unresolved) * 0.15

        # Boost score slightly for historical success.
        success_rate = -1.0
        if self.cbkb is not None and plan.strategy_name:
            success_rate = self.cbkb.get_strategy_success_rate(
                plan.strategy_name, template_id=template_id
            )
            if success_rate >= 0:
                score = score * 0.8 + success_rate * 0.2

        score = max(0.0, min(1.0, score))

        return PlanQualityReport(
            score=round(score, 3),
            valid=validation.valid and len(unresolved) == 0,
            findings=findings,
            strategy_success_rate=success_rate,
        )
