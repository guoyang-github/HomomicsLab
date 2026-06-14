"""DynamicReplanningEngine — adaptive plan modification based on runtime triggers.

The DynamicReplanningEngine sits downstream of PlanEngine and InterpretationEngine.
When anomalies are detected, data quality changes, skills fail, or the user intervenes,
this engine mutates the current PlanResult to produce an adapted plan.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult


@dataclass
class ReplanningTrigger:
    """A trigger that initiates dynamic replanning."""

    trigger_type: str  # "anomaly_detected" | "data_state_changed" | "user_intervention" | "skill_failure" | "phase_gate_fail"
    context: Dict[str, Any] = field(default_factory=dict)
    severity: str = "minor"  # "minor" | "major" | "critical"

    def __post_init__(self):
        if self.trigger_type not in (
            "anomaly_detected",
            "data_state_changed",
            "user_intervention",
            "skill_failure",
            "phase_gate_fail",
        ):
            raise ValueError(f"Invalid trigger_type: {self.trigger_type}")
        if self.severity not in ("minor", "major", "critical"):
            raise ValueError(f"Invalid severity: {self.severity}")


@dataclass
class PlanDelta:
    """Describes the set of changes applied to a plan."""

    phases_to_insert: List[Phase] = field(default_factory=list)
    phases_to_remove: List[int] = field(default_factory=list)
    phases_to_modify: List[Tuple[int, Dict[str, Any]]] = field(default_factory=list)
    reason: str = ""


class DynamicReplanningEngine:
    """Adapts analysis plans in response to runtime triggers.

    Usage:
        engine = DynamicReplanningEngine(plan_engine, skill_dag)
        new_plan = engine.replan(current_plan, triggers, data_state)
    """

    def __init__(
        self,
        plan_engine: PlanEngine,
        skill_dag: Optional[Any] = None,
    ):
        self.plan_engine = plan_engine
        self.skill_dag = skill_dag

    def replan(
        self,
        current_plan: PlanResult,
        triggers: List[ReplanningTrigger],
        data_state: DataState,
    ) -> PlanResult:
        """Apply replanning triggers to modify the current plan.

        Returns a new PlanResult with the adapted phase sequence.
        """
        new_plan = PlanResult(
            phases=[self._copy_phase(p) for p in current_plan.phases],
            strategy_name=current_plan.strategy_name,
            data_state=data_state,
            gaps=list(current_plan.gaps),
            reproducibility_context=dict(current_plan.reproducibility_context),
        )

        delta = PlanDelta()

        for trigger in triggers:
            if trigger.trigger_type == "anomaly_detected":
                self._handle_anomaly(new_plan, trigger, delta)
            elif trigger.trigger_type == "data_state_changed":
                self._handle_data_state_change(new_plan, trigger, data_state, delta)
            elif trigger.trigger_type == "skill_failure":
                self._handle_skill_failure(new_plan, trigger, delta)
            elif trigger.trigger_type == "user_intervention":
                self._handle_user_intervention(new_plan, trigger, delta)
            elif trigger.trigger_type == "phase_gate_fail":
                self._handle_phase_gate_fail(new_plan, trigger, delta)

        new_plan.reproducibility_context.update(
            {
                "replanned": True,
                "replanning_delta": {
                    "phases_inserted": len(delta.phases_to_insert),
                    "phases_removed": len(delta.phases_to_remove),
                    "phases_modified": len(delta.phases_to_modify),
                    "reason": delta.reason.strip(),
                },
            }
        )

        return new_plan

    @staticmethod
    def _copy_phase(phase: Phase) -> Phase:
        """Create a deep copy of a phase."""
        return Phase(
            phase_type=phase.phase_type,
            required=phase.required,
            description=phase.description,
            selected_skill=phase.selected_skill,
            parameters=dict(phase.parameters),
            agent_code=phase.agent_code,
        )

    @staticmethod
    def _insert_phase(current_plan: PlanResult, index: int, phase: Phase) -> None:
        """Insert a phase at the given index."""
        current_plan.phases.insert(index, phase)

    @staticmethod
    def _remove_phase(current_plan: PlanResult, index: int) -> None:
        """Remove a phase at the given index."""
        if 0 <= index < len(current_plan.phases):
            current_plan.phases.pop(index)

    def _find_alternative_skill(
        self,
        skill_id: str,
        skill_dag: Optional[Any] = None,
    ) -> Optional[str]:
        """Find an alternative skill via SkillDAG.

        Returns the highest-confidence alternative skill ID, or None.
        """
        dag = skill_dag or self.skill_dag
        if dag is None:
            return None

        alternatives = dag.get_alternatives(skill_id)
        if not alternatives:
            return None

        # Pick the highest-confidence alternative
        alternatives.sort(key=lambda x: x[1], reverse=True)
        return alternatives[0][0]

    # ─────────────────────────────────────────
    # Trigger handlers
    # ─────────────────────────────────────────

    def _handle_anomaly(
        self,
        plan: PlanResult,
        trigger: ReplanningTrigger,
        delta: PlanDelta,
    ) -> None:
        """Handle anomaly_detected triggers."""
        if trigger.severity != "critical":
            return

        phase_type = trigger.context.get("phase_type")
        if phase_type != "qc":
            return

        # Find the QC phase and insert a re-QC phase after it
        for i, phase in enumerate(plan.phases):
            if phase.phase_type == "qc":
                re_qc = Phase(
                    phase_type="qc",
                    required=True,
                    description="Re-QC with tighter parameters",
                    parameters={
                        "tight_mode": True,
                        **trigger.context.get("extra_params", {}),
                    },
                )
                self._insert_phase(plan, i + 1, re_qc)
                delta.phases_to_insert.append(re_qc)
                delta.reason += "Inserted re-QC after QC due to critical anomaly. "
                break

    def _handle_data_state_change(
        self,
        plan: PlanResult,
        trigger: ReplanningTrigger,
        data_state: DataState,
        delta: PlanDelta,
    ) -> None:
        """Handle data_state_changed triggers."""
        change_type = trigger.context.get("change_type")
        if change_type == "batch_effect":
            # Insert integration phase before differential_expression
            de_idx = None
            for i, phase in enumerate(plan.phases):
                if phase.phase_type == "differential_expression":
                    de_idx = i
                    break

            if de_idx is not None:
                integration_phase = Phase(
                    phase_type="integration",
                    required=True,
                    description="Batch integration / correction",
                    parameters=trigger.context.get("params", {}),
                )
                self._insert_phase(plan, de_idx, integration_phase)
                delta.phases_to_insert.append(integration_phase)
                delta.reason += "Inserted integration before DE due to batch effect. "

    def _handle_skill_failure(
        self,
        plan: PlanResult,
        trigger: ReplanningTrigger,
        delta: PlanDelta,
    ) -> None:
        """Handle skill_failure triggers."""
        failed_skill_id = trigger.context.get("failed_skill_id")
        if not failed_skill_id:
            return

        alt_skill_id = self._find_alternative_skill(failed_skill_id)
        if alt_skill_id is None:
            delta.reason += f"No alternative found for failed skill {failed_skill_id}. "
            return

        # Find the phase with the failed skill and swap it
        for i, phase in enumerate(plan.phases):
            if phase.selected_skill is not None and phase.selected_skill.id == failed_skill_id:
                # Get alternative skill definition from registry
                alt_skill = None
                if self.skill_dag is not None:
                    alt_skill = self.skill_dag.registry.get(alt_skill_id)

                phase.selected_skill = alt_skill
                delta.phases_to_modify.append((i, {"selected_skill": alt_skill_id}))
                delta.reason += f"Swapped failed skill {failed_skill_id} with {alt_skill_id}. "
                break

    def _handle_user_intervention(
        self,
        plan: PlanResult,
        trigger: ReplanningTrigger,
        delta: PlanDelta,
    ) -> None:
        """Handle user_intervention triggers."""
        target_phase_type = trigger.context.get("phase_type")
        new_params = trigger.context.get("new_params", {})

        if not target_phase_type or not new_params:
            return

        target_idx = None
        for i, phase in enumerate(plan.phases):
            if phase.phase_type == target_phase_type:
                target_idx = i
                phase.parameters.update(new_params)
                delta.phases_to_modify.append((i, dict(new_params)))
                break

        if target_idx is None:
            return

        # Propagate parameter changes to downstream phases
        propagated_keys = trigger.context.get("propagate_keys", list(new_params.keys()))
        for i in range(target_idx + 1, len(plan.phases)):
            for key in propagated_keys:
                if key in plan.phases[i].parameters:
                    plan.phases[i].parameters[key] = new_params[key]
                    delta.phases_to_modify.append((i, {key: new_params[key]}))

        delta.reason += f"Propagated user parameter changes from {target_phase_type}. "

    def _handle_phase_gate_fail(
        self,
        plan: PlanResult,
        trigger: ReplanningTrigger,
        delta: PlanDelta,
    ) -> None:
        """Handle phase_gate_fail triggers by inserting a remediation phase."""
        phase_type = trigger.context.get("phase_type")
        remediation = trigger.context.get("remediation", "re_qc")

        if phase_type is None:
            return

        if remediation == "re_qc":
            for i, phase in enumerate(plan.phases):
                if phase.phase_type == phase_type:
                    re_phase = Phase(
                        phase_type="qc",
                        required=True,
                        description="Re-QC with tighter parameters",
                        parameters=trigger.context.get("extra_params", {}),
                        selected_skill=phase.selected_skill,
                    )
                    self._insert_phase(plan, i + 1, re_phase)
                    delta.phases_to_insert.append(re_phase)
                    delta.reason += (
                        f"Inserted re-qc after {phase_type} due to phase gate fail. "
                    )
                    break
        elif remediation == "insert_after":
            insert_phase_type = trigger.context.get("insert_phase_type", "qc")
            after_phase_type = trigger.context.get("after_phase_type", phase_type)
            for i, phase in enumerate(plan.phases):
                if phase.phase_type == after_phase_type:
                    new_phase = Phase(
                        phase_type=insert_phase_type,
                        required=True,
                        description=trigger.context.get(
                            "description",
                            f"Remediation {insert_phase_type} after {after_phase_type}",
                        ),
                        parameters=trigger.context.get("extra_params", {}),
                    )
                    self._insert_phase(plan, i + 1, new_phase)
                    delta.phases_to_insert.append(new_phase)
                    delta.reason += (
                        f"Inserted {insert_phase_type} after {after_phase_type} "
                        f"due to phase gate fail. "
                    )
                    break
