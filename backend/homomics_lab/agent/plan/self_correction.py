"""Controlled self-correction for plan execution.

When runtime triggers (skill failure, phase gate failure, data state change,
anomaly) occur, the SelfCorrectionEngine decides whether to replan
automatically, ask for human approval, or stop. It produces a human-readable
delta summary so the user can understand what changed and why.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.replanning import (
    DynamicReplanningEngine,
    PlanDelta,
    ReplanningTrigger,
)


class SelfCorrectionAction:
    """Possible self-correction decisions."""

    AUTO_REPLAN = "auto_replan"
    HITL_REPLAN = "hitl_replan"
    STOP = "stop"


@dataclass
class SelfCorrectionDecision:
    """Result of a self-correction evaluation."""

    action: str  # SelfCorrectionAction value
    severity: str
    triggers: List[ReplanningTrigger]
    new_plan: Optional[PlanResult] = None
    delta: Optional[PlanDelta] = None
    delta_summary: str = ""
    reason: str = ""


@dataclass
class SelfCorrectionPolicy:
    """Policy mapping trigger severity to self-correction action."""

    auto_severity: List[str] = field(default_factory=lambda: ["minor"])
    hitl_severity: List[str] = field(default_factory=lambda: ["major"])
    stop_severity: List[str] = field(default_factory=lambda: ["critical"])

    def decide(self, severity: str) -> str:
        """Return the action for a given severity."""
        if severity in self.auto_severity:
            return SelfCorrectionAction.AUTO_REPLAN
        if severity in self.hitl_severity:
            return SelfCorrectionAction.HITL_REPLAN
        if severity in self.stop_severity:
            return SelfCorrectionAction.STOP
        # Default: treat unknown severity as requiring approval.
        return SelfCorrectionAction.HITL_REPLAN


class SelfCorrectionEngine:
    """Evaluate runtime triggers and decide how to correct a plan."""

    def __init__(
        self,
        replanning_engine: DynamicReplanningEngine,
        policy: Optional[SelfCorrectionPolicy] = None,
    ):
        self.replanning_engine = replanning_engine
        self.policy = policy or SelfCorrectionPolicy()

    def evaluate(
        self,
        current_plan: PlanResult,
        triggers: List[ReplanningTrigger],
        data_state: Optional[DataState] = None,
    ) -> SelfCorrectionDecision:
        """Decide how to correct ``current_plan`` given ``triggers``.

        Args:
            current_plan: The plan currently being executed.
            triggers: Runtime replanning triggers.
            data_state: Current data state.

        Returns:
            A ``SelfCorrectionDecision`` describing the chosen action, the
            replanned plan (if any), and a human-readable delta summary.
        """
        if not triggers:
            return SelfCorrectionDecision(
                action=SelfCorrectionAction.AUTO_REPLAN,
                severity="minor",
                triggers=[],
                new_plan=current_plan,
                reason="No triggers; nothing to correct.",
            )

        # Use the most severe trigger to decide the action.
        severity_order = {"minor": 0, "major": 1, "critical": 2}
        max_trigger = max(
            triggers,
            key=lambda t: severity_order.get(t.severity, 1),
        )
        severity = max_trigger.severity
        action = self.policy.decide(severity)

        if action == SelfCorrectionAction.STOP:
            return SelfCorrectionDecision(
                action=action,
                severity=severity,
                triggers=triggers,
                reason=self._build_reason(triggers),
            )

        data_state = data_state or current_plan.data_state or DataState()
        new_plan = self.replanning_engine.replan(
            current_plan,
            triggers,
            data_state,
        )
        delta = self._compute_delta(current_plan, new_plan)
        delta_summary = self._build_delta_summary(delta)

        return SelfCorrectionDecision(
            action=action,
            severity=severity,
            triggers=triggers,
            new_plan=new_plan,
            delta=delta,
            delta_summary=delta_summary,
            reason=self._build_reason(triggers),
        )

    @staticmethod
    def _build_reason(triggers: List[ReplanningTrigger]) -> str:
        """Build a concise reason string from triggers."""
        reasons = []
        for trigger in triggers:
            reason = trigger.context.get("reason", "")
            if not reason:
                reason = f"{trigger.trigger_type} ({trigger.severity})"
            reasons.append(reason)
        return "; ".join(reasons) if reasons else "Runtime trigger activated replanning."

    @staticmethod
    def _compute_delta(old_plan: PlanResult, new_plan: PlanResult) -> PlanDelta:
        """Compute the structural delta between two plans."""
        old_types = [p.phase_type for p in old_plan.phases]
        new_types = [p.phase_type for p in new_plan.phases]

        inserted: List[Phase] = []
        removed: List[int] = []
        modified: List[Any] = []

        old_index = {p.phase_type: i for i, p in enumerate(old_plan.phases)}
        new_index = {p.phase_type: i for i, p in enumerate(new_plan.phases)}

        for i, phase_type in enumerate(new_types):
            if phase_type not in old_index:
                inserted.append(new_plan.phases[i])

        for i, phase_type in enumerate(old_types):
            if phase_type not in new_index:
                removed.append(i)
            else:
                old_phase = old_plan.phases[i]
                new_phase = new_plan.phases[new_index[phase_type]]
                if old_phase.selected_skill != new_phase.selected_skill:
                    modified.append(
                        {
                            "index": i,
                            "phase_type": phase_type,
                            "old_skill": (
                                old_phase.selected_skill.id
                                if old_phase.selected_skill
                                else None
                            ),
                            "new_skill": (
                                new_phase.selected_skill.id
                                if new_phase.selected_skill
                                else None
                            ),
                        }
                    )

        return PlanDelta(
            phases_to_insert=inserted,
            phases_to_remove=removed,
            phases_to_modify=modified,
            reason=SelfCorrectionEngine._build_reason([]),
        )

    @staticmethod
    def _build_delta_summary(delta: PlanDelta) -> str:
        """Build a human-readable summary of the plan delta."""
        parts: List[str] = []
        if delta.phases_to_insert:
            names = [p.phase_type for p in delta.phases_to_insert]
            parts.append(f"新增步骤：{', '.join(names)}")
        if delta.phases_to_remove:
            parts.append(f"移除 {len(delta.phases_to_remove)} 个步骤")
        if delta.phases_to_modify:
            names = [m["phase_type"] for m in delta.phases_to_modify]
            parts.append(f"调整工具：{', '.join(names)}")
        if not parts:
            return "计划已重新评估，结构无明显变化。"
        return "；".join(parts)
