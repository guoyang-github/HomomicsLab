"""Tests for plan quality evaluation and CBKB feedback loop."""

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.quality import PlanQualityEvaluator
from homomics_lab.agent.plan.validator import PlanValidator
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillOutputSchema
from homomics_lab.skills.registry import SkillRegistry


class TestPlanQualityEvaluator:
    def test_high_score_for_fully_resolved_plan(self, tmp_path):
        reg = SkillRegistry()
        reg.register(
            SkillDefinition(
                id="scanpy_qc",
                name="QC",
                version="1.0",
                category="single-cell",
                description="QC",
                input_schema=SkillInputSchema(),
                output_schema=SkillOutputSchema(),
                runtime={"type": "python", "dependencies": ["scanpy"]},
            )
        )
        plan = PlanResult(
            phases=[
                Phase(
                    phase_type="qc",
                    selected_skill=reg.get("scanpy_qc"),
                    parameters={"min_genes": 200},
                ),
            ],
            strategy_name="single-cell-transcriptomics",
            data_state=DataState(),
        )
        evaluator = PlanQualityEvaluator(PlanValidator(reg))
        report = evaluator.evaluate(plan)
        assert report.valid is True
        assert report.score > 0.7

    def test_low_score_for_unresolved_phases(self):
        reg = SkillRegistry()
        plan = PlanResult(
            phases=[Phase(phase_type="qc")],
            strategy_name="single-cell-transcriptomics",
            data_state=DataState(),
        )
        evaluator = PlanQualityEvaluator(PlanValidator(reg))
        report = evaluator.evaluate(plan)
        assert report.valid is False
        assert report.score < 1.0

    def test_strategy_success_rate_from_cbkb(self, tmp_path):
        reg = SkillRegistry()
        cbkb = CBKB(tmp_path)
        cbkb.record_plan_outcome(
            plan_id=None,
            strategy_name="single-cell-transcriptomics",
            success=True,
            template_id=None,
        )
        cbkb.record_plan_outcome(
            plan_id=None,
            strategy_name="single-cell-transcriptomics",
            success=False,
            template_id=None,
        )

        skill = SkillDefinition(
            id="scanpy_qc",
            name="QC",
            version="1.0",
            category="single-cell",
            input_schema=SkillInputSchema(),
            output_schema=SkillOutputSchema(),
            runtime={"type": "python", "dependencies": ["scanpy"]},
        )
        reg.register(skill)
        plan = PlanResult(
            phases=[Phase(phase_type="qc", selected_skill=skill)],
            strategy_name="single-cell-transcriptomics",
            data_state=DataState(),
        )
        evaluator = PlanQualityEvaluator(PlanValidator(reg), cbkb=cbkb)
        report = evaluator.evaluate(plan)
        assert report.strategy_success_rate == 0.5
