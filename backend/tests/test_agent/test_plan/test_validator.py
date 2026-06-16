"""Tests for PlanValidator."""

import pytest

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult, PlannedGap
from homomics_lab.agent.plan.validator import PlanValidationIssue, PlanValidator
from homomics_lab.skills.models import (
    SkillDefinition,
    SkillInputSchema,
    SkillOutputSchema,
    SkillRuntime,
)
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def registry():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            description="Quality control",
            input_schema=SkillInputSchema(
                properties={"adata": {"type": "string"}},
                required=["adata"],
            ),
            output_schema=SkillOutputSchema(
                properties={"qc_adata": {"type": "string"}},
            ),
            runtime=SkillRuntime(dependencies=["scanpy"]),
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_normalize",
            name="scanpy_normalize",
            version="1.0",
            category="single_cell",
            description="Normalization",
            input_schema=SkillInputSchema(
                properties={"qc_adata": {"type": "string"}},
                required=["qc_adata"],
            ),
            output_schema=SkillOutputSchema(
                properties={"normalized_adata": {"type": "string"}},
            ),
            runtime=SkillRuntime(dependencies=["scanpy"]),
        )
    )
    return reg


class TestPlanValidator:
    def test_valid_plan(self, registry):
        validator = PlanValidator(registry)
        plan = PlanResult(
            phases=[
                Phase(
                    phase_type="qc",
                    selected_skill=registry.get("scanpy_qc"),
                    parameters={"adata": "raw.h5ad"},
                ),
                Phase(
                    phase_type="normalization",
                    selected_skill=registry.get("scanpy_normalize"),
                ),
            ],
            strategy_name="single_cell",
            data_state=DataState(),
        )

        report = validator.validate(plan)

        assert report.valid is True
        assert not report.errors

    def test_missing_skill_error(self, registry):
        validator = PlanValidator(registry)
        unregistered = SkillDefinition(
            id="missing_skill",
            name="missing_skill",
            version="1.0",
            category="single_cell",
        )
        plan = PlanResult(
            phases=[Phase(phase_type="qc", selected_skill=unregistered)],
            strategy_name="single_cell",
            data_state=DataState(),
        )

        report = validator.validate(plan)

        assert report.valid is False
        assert any(e.skill_id == "missing_skill" for e in report.errors)

    def test_missing_input_warning(self, registry):
        validator = PlanValidator(registry)
        plan = PlanResult(
            phases=[
                Phase(
                    phase_type="qc",
                    selected_skill=registry.get("scanpy_qc"),
                    parameters={},
                )
            ],
            strategy_name="single_cell",
            data_state=DataState(),
        )

        report = validator.validate(plan)

        assert any(
            "adata" in w.message and w.skill_id == "scanpy_qc"
            for w in report.warnings
        )

    def test_gap_warning(self, registry):
        validator = PlanValidator(registry)
        plan = PlanResult(
            phases=[
                Phase(phase_type="qc", selected_skill=registry.get("scanpy_qc"))
            ],
            strategy_name="single_cell",
            data_state=DataState(),
            gaps=[
                PlannedGap(
                    from_phase="qc",
                    to_phase="normalization",
                    from_skill="scanpy_qc",
                    to_skill="scanpy_normalize",
                    gap_type="format_conversion",
                )
            ],
        )

        report = validator.validate(plan)

        assert any("format_conversion" in w.message for w in report.warnings)

    def test_optional_phase_without_skill_is_ok(self, registry):
        validator = PlanValidator(registry)
        plan = PlanResult(
            phases=[Phase(phase_type="visualization", required=False)],
            strategy_name="single_cell",
            data_state=DataState(),
        )

        report = validator.validate(plan)

        assert report.valid is True

    def test_validate_dependencies_installed(self, registry):
        validator = PlanValidator(registry)
        plan = PlanResult(
            phases=[
                Phase(
                    phase_type="qc",
                    selected_skill=registry.get("scanpy_qc"),
                )
            ],
            strategy_name="single_cell",
            data_state=DataState(),
        )

        missing = validator.validate_dependencies_installed(plan)

        # scanpy should be importable in the test environment
        assert "scanpy" not in missing

    def test_dataclass_report_helpers(self):
        report = PlanValidator(SkillRegistry()).validate(
            PlanResult(phases=[], strategy_name="empty", data_state=DataState())
        )
        report.add_warning("warn", phase="p1", skill_id="s1")
        assert len(report.warnings) == 1
        assert isinstance(report.warnings[0], PlanValidationIssue)
