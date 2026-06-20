"""Plan validation — intercept invalid plans before execution.

Checks:
  1. All referenced skills exist in the registry.
  2. Required inputs for each phase are satisfiable (from data state or previous outputs).
  3. Schema gaps between consecutive phases are detected and reported.
  4. Runtime dependencies are declared (best-effort availability check).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from homomics_lab.agent.plan.models import DataState, PlanResult
from homomics_lab.skills.registry import SkillRegistry


@dataclass
class PlanValidationIssue:
    """A single plan validation issue."""

    severity: str  # "error" | "warning"
    phase: Optional[str]
    skill_id: Optional[str]
    message: str


@dataclass
class PlanValidationReport:
    """Result of validating a plan."""

    valid: bool
    errors: List[PlanValidationIssue] = field(default_factory=list)
    warnings: List[PlanValidationIssue] = field(default_factory=list)

    def add_error(self, message: str, phase: Optional[str] = None, skill_id: Optional[str] = None) -> None:
        self.errors.append(PlanValidationIssue("error", phase, skill_id, message))
        self.valid = False

    def add_warning(self, message: str, phase: Optional[str] = None, skill_id: Optional[str] = None) -> None:
        self.warnings.append(PlanValidationIssue("warning", phase, skill_id, message))


class PlanValidator:
    """Validate generated plans before execution."""

    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry

    def validate(
        self,
        plan: PlanResult,
        data_state: Optional[DataState] = None,
    ) -> PlanValidationReport:
        """Validate a plan and return a report."""
        report = PlanValidationReport(valid=True)
        data_state = data_state or plan.data_state or DataState()

        available_outputs: Dict[str, Any] = {}
        if hasattr(data_state, "domain_state") and isinstance(data_state.domain_state, dict):
            for values in data_state.domain_state.values():
                if isinstance(values, dict):
                    available_outputs.update(values)

        for phase in plan.phases:
            if not phase.required and phase.selected_skill is None:
                # Optional phases may be skipped
                continue

            if phase.selected_skill is None:
                report.add_error(
                    f"Phase '{phase.phase_type}' has no selected skill",
                    phase=phase.phase_type,
                )
                continue

            skill_id = phase.selected_skill.id

            # 1. Skill existence
            if self.skill_registry.get(skill_id) is None:
                report.add_error(
                    f"Skill '{skill_id}' is not registered",
                    phase=phase.phase_type,
                    skill_id=skill_id,
                )
                continue

            # 2. Required inputs
            input_schema = phase.selected_skill.input_schema
            for required_field in input_schema.required:
                if required_field in available_outputs:
                    continue
                if hasattr(data_state, required_field):
                    continue
                if hasattr(data_state, "domain_state") and isinstance(data_state.domain_state, dict):
                    if any(required_field in v for v in data_state.domain_state.values() if isinstance(v, dict)):
                        continue
                report.add_warning(
                    f"Required input '{required_field}' for skill '{skill_id}' may be missing",
                    phase=phase.phase_type,
                    skill_id=skill_id,
                )

            # 3. Dependencies declared
            if not phase.selected_skill.runtime.dependencies:
                report.add_warning(
                    f"Skill '{skill_id}' has no declared dependencies",
                    phase=phase.phase_type,
                    skill_id=skill_id,
                )

            # Accumulate outputs for downstream phases
            for output_name in phase.selected_skill.output_schema.properties.keys():
                available_outputs[output_name] = f"<output from {skill_id}>"

        # 4. Schema gaps (already detected by PlanEngine)
        for gap in plan.gaps:
            if gap.gap_type != "none":
                report.add_warning(
                    f"Schema gap between '{gap.from_phase}' and '{gap.to_phase}': {gap.gap_type}",
                    phase=gap.to_phase,
                )

        return report

    def validate_dependencies_installed(
        self,
        plan: PlanResult,
    ) -> Set[str]:
        """Best-effort check for which declared dependencies are importable.

        Returns a set of dependency specifiers that appear to be missing.
        """
        missing: Set[str] = set()
        for phase in plan.phases:
            if phase.selected_skill is None:
                continue
            for dep in phase.selected_skill.runtime.dependencies:
                pkg_name = dep.split("[")[0].split("=")[0].split(">")[0].split("<")[0].strip()
                if not pkg_name:
                    continue
                try:
                    __import__(pkg_name)
                except ImportError:
                    missing.add(dep)
        return missing
