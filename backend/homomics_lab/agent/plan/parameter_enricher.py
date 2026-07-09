"""Parameter enrichment and validation for planned phases.

Each selected skill declares an input schema with defaults, constraints and
anti-hallucination metadata (``source``, ``range``, ``rationale``).
``ParameterEnricher`` uses this schema to:

1. Fill missing parameters with skill defaults.
2. Record the provenance of every parameter value.
3. Build human-readable recommendations for the UI.
4. Validate parameter values against schema constraints.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.validator import PlanValidationReport
from homomics_lab.skills.capability_index import CapabilityIndex, CapabilityType
from homomics_lab.skills.models import SkillDefinition

logger = logging.getLogger(__name__)


@dataclass
class ParameterMetadata:
    """Structured metadata for a single plan parameter."""

    name: str
    value: Any = None
    source: str = "unknown"
    range: str = ""
    rationale: str = ""
    default: Any = None
    required: bool = False


class ParameterEnricher:
    """Enrich phase parameters using skill input schemas and parameter lore."""

    def __init__(
        self,
        capability_index: Optional[CapabilityIndex] = None,
    ) -> None:
        self.capability_index = capability_index

    def enrich_phase(self, phase: Phase) -> None:
        """Fill defaults, recommendations, sources and metadata for ``phase``."""
        if phase.selected_skill is None:
            return

        schema = phase.selected_skill.input_schema
        schema_props = schema.properties or {}
        if not schema_props:
            return

        required = set(schema.required or [])

        # Fill missing defaults first so downstream metadata sees them.
        for name, prop in schema_props.items():
            if name not in phase.parameters and "default" in prop:
                phase.parameters[name] = prop["default"]
                phase.parameter_sources[name] = "skill_default"

        # Build recommendations and record source for every declared parameter.
        for name, prop in schema_props.items():
            meta = self._extract_metadata(name, prop, name in required)
            if name not in phase.parameter_sources:
                phase.parameter_sources[name] = meta.source
            phase.parameter_recommendations[name] = self._build_recommendation(meta)

    def enrich_plan(self, plan: PlanResult) -> None:
        """Enrich every phase in ``plan``."""
        for phase in plan.phases:
            self.enrich_phase(phase)

    async def enrich_plan_with_lore(self, plan: PlanResult) -> None:
        """Augment every phase with parameter lore from the capability index."""
        for phase in plan.phases:
            await self.enrich_phase_with_lore(phase)

    async def enrich_phase_with_lore(self, phase: Phase) -> None:
        """Augment ``phase`` with parameter lore retrieved from the capability index."""
        if phase.selected_skill is None or self.capability_index is None:
            return

        schema_props = phase.selected_skill.input_schema.properties or {}
        for name in schema_props:
            try:
                lore_results = await self.capability_index.search(
                    query=f"{phase.selected_skill.id} {name} parameter best practice",
                    top_k=1,
                    item_types=[CapabilityType.PARAMETER_LORE],
                )
                if not lore_results:
                    continue
                lore = lore_results[0].payload.get("lore", {})
                if not lore:
                    continue
                meta = ParameterMetadata(
                    name=name,
                    source=lore.get("source", "lore"),
                    range=lore.get("range", ""),
                    rationale=lore.get("rationale", ""),
                    default=lore.get("default"),
                )
                if meta.rationale and name not in phase.parameter_recommendations:
                    phase.parameter_recommendations[name] = self._build_recommendation(meta)
                if meta.source and name not in phase.parameter_sources:
                    phase.parameter_sources[name] = meta.source
            except Exception as exc:
                logger.warning(
                    "Failed to retrieve lore for %s:%s: %s",
                    phase.selected_skill.id,
                    name,
                    exc,
                )

    @staticmethod
    def _extract_metadata(name: str, prop: Dict[str, Any], required: bool) -> ParameterMetadata:
        """Extract structured metadata from a JSON-Schema property."""
        return ParameterMetadata(
            name=name,
            value=prop.get("default"),
            source=prop.get("source", "unknown"),
            range=prop.get("range", ""),
            rationale=prop.get("rationale", ""),
            default=prop.get("default"),
            required=required,
        )

    @staticmethod
    def _build_recommendation(meta: ParameterMetadata) -> str:
        """Build a concise human-readable recommendation string."""
        parts: List[str] = []
        if meta.rationale:
            parts.append(meta.rationale)
        if meta.range:
            parts.append(f"有效范围: {meta.range}")
        if meta.default is not None:
            parts.append(f"默认值: {meta.default}")
        if meta.source and meta.source != "unknown":
            parts.append(f"来源: {meta.source}")
        return "；".join(parts) if parts else ""

    @staticmethod
    def validate_plan_parameters(
        plan: PlanResult,
        data_state: Optional[DataState] = None,
    ) -> PlanValidationReport:
        """Validate all phase parameters against skill input schemas."""
        report = PlanValidationReport(valid=True)
        available: Dict[str, Any] = {}
        if data_state is not None and hasattr(data_state, "domain_state"):
            for values in data_state.domain_state.values():
                if isinstance(values, dict):
                    available.update(values)

        for phase in plan.phases:
            if not phase.required or phase.selected_skill is None:
                continue

            skill = phase.selected_skill
            schema_props = skill.input_schema.properties or {}
            required = set(skill.input_schema.required or [])

            for name, prop in schema_props.items():
                value = phase.parameters.get(name)
                if value is None:
                    if name in required and name not in available:
                        report.add_warning(
                            f"缺少必填参数 '{name}'",
                            phase=phase.phase_type,
                            skill_id=skill.id,
                        )
                    continue

                try:
                    SkillDefinition._validate_parameter(name, prop, value)
                except ValueError as exc:
                    report.add_error(
                        str(exc),
                        phase=phase.phase_type,
                        skill_id=skill.id,
                    )

        return report

    def merge_validation_reports(
        self,
        base: PlanValidationReport,
        parameter_report: PlanValidationReport,
    ) -> PlanValidationReport:
        """Merge a parameter validation report into ``base``."""
        for issue in parameter_report.errors:
            base.add_error(issue.message, phase=issue.phase, skill_id=issue.skill_id)
        for issue in parameter_report.warnings:
            base.add_warning(issue.message, phase=issue.phase, skill_id=issue.skill_id)
        return base
