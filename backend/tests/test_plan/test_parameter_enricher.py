"""Tests for ParameterEnricher."""

import pytest

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.parameter_enricher import ParameterEnricher
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema


def _make_skill_with_schema(properties: dict, required: list = None) -> SkillDefinition:
    return SkillDefinition(
        id="test_skill",
        name="Test Skill",
        version="1.0",
        category="test",
        input_schema=SkillInputSchema(properties=properties, required=required or []),
    )


def test_enrich_phase_fills_defaults():
    skill = _make_skill_with_schema(
        properties={
            "resolution": {
                "type": "number",
                "default": 1.0,
                "range": "0.1 - 2.0",
                "rationale": "Clustering resolution",
            },
            "n_genes": {"type": "integer"},
        },
    )
    phase = Phase(phase_type="clustering", selected_skill=skill)
    enricher = ParameterEnricher()

    enricher.enrich_phase(phase)

    assert phase.parameters["resolution"] == 1.0
    assert phase.parameter_sources["resolution"] == "skill_default"
    assert "默认值: 1.0" in phase.parameter_recommendations["resolution"]
    assert phase.parameter_sources["n_genes"] == "unknown"


def test_enrich_phase_preserves_user_provided_values():
    skill = _make_skill_with_schema(
        properties={
            "resolution": {
                "type": "number",
                "default": 1.0,
                "source": "user",
            },
        },
    )
    phase = Phase(
        phase_type="clustering",
        selected_skill=skill,
        parameters={"resolution": 0.8},
    )
    enricher = ParameterEnricher()

    enricher.enrich_phase(phase)

    assert phase.parameters["resolution"] == 0.8
    assert phase.parameter_sources["resolution"] == "user"


def test_validate_plan_parameters_reports_missing_required():
    skill = _make_skill_with_schema(
        properties={
            "input_file": {"type": "string"},
            "output_file": {"type": "string"},
        },
        required=["input_file"],
    )
    plan = PlanResult(
        phases=[Phase(phase_type="convert", selected_skill=skill)],
        strategy_name="test",
        data_state=DataState(),
    )
    enricher = ParameterEnricher()

    report = enricher.validate_plan_parameters(plan)

    assert any("input_file" in w.message for w in report.warnings)


def test_validate_plan_parameters_reports_constraint_violations():
    skill = _make_skill_with_schema(
        properties={
            "resolution": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 2.0,
            },
        },
    )
    plan = PlanResult(
        phases=[
            Phase(
                phase_type="clustering",
                selected_skill=skill,
                parameters={"resolution": 5.0},
            )
        ],
        strategy_name="test",
        data_state=DataState(),
    )
    enricher = ParameterEnricher()

    report = enricher.validate_plan_parameters(plan)

    assert not report.valid
    assert any("resolution" in e.message for e in report.errors)


def test_merge_validation_reports():
    enricher = ParameterEnricher()
    base = enricher.validate_plan_parameters(
        PlanResult(phases=[], strategy_name="test", data_state=DataState())
    )
    parameter_report = enricher.validate_plan_parameters(
        PlanResult(phases=[], strategy_name="test", data_state=DataState())
    )
    parameter_report.add_warning("test warning", phase="p1")

    merged = enricher.merge_validation_reports(base, parameter_report)

    assert any(w.message == "test warning" and w.phase == "p1" for w in merged.warnings)


@pytest.mark.asyncio
async def test_enrich_phase_with_lore_uses_capability_index():
    from homomics_lab.skills.capability_index import CapabilityCandidate, CapabilityType

    class FakeIndex:
        async def search(self, query: str, top_k: int = 1, item_types=None):
            if "resolution" in query:
                return [
                    CapabilityCandidate(
                        id="test_skill:resolution",
                        type=CapabilityType.PARAMETER_LORE,
                        name="resolution",
                        description="",
                        category="parameter_lore",
                        score=0.9,
                        payload={
                            "lore": {
                                "rationale": "Use 0.4-1.2 for small datasets",
                                "source": "cbkb",
                            }
                        },
                    )
                ]
            return []

    skill = _make_skill_with_schema(properties={"resolution": {"type": "number"}})
    phase = Phase(phase_type="clustering", selected_skill=skill)
    enricher = ParameterEnricher(capability_index=FakeIndex())

    await enricher.enrich_phase_with_lore(phase)

    assert "small datasets" in phase.parameter_recommendations.get("resolution", "")
    assert phase.parameter_sources.get("resolution") == "cbkb"
