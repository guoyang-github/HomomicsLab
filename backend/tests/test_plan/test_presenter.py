"""Tests for PlanPresenter summaries and payloads."""

import pytest

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.plan.models import Plan
from homomics_lab.plan.presenter import PlanPresenter
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.tasks.task_tree import TaskTree


def _make_plan(is_fallback: bool = False, phase_count: int = 3) -> Plan:
    skill = SkillDefinition(
        id="scanpy_qc",
        name="QC",
        version="1.0",
        category="single_cell",
        description="Quality control",
        input_schema=SkillInputSchema(),
    )
    phases = [
        Phase(
            phase_type=f"phase_{i}",
            description=f"Step {i + 1}",
            selected_skill=skill,
        )
        for i in range(phase_count)
    ]
    return Plan(
        plan_id="plan_1",
        session_id="sess_1",
        project_id="proj_1",
        intent_analysis_type="single_cell_analysis",
        is_fallback=is_fallback,
        plan_result=PlanResult(phases=phases, strategy_name="test", data_state=DataState()),
        task_tree=TaskTree(tasks=[]),
    )


class TestPlanSummary:
    @pytest.mark.asyncio
    async def test_fallback_summary_uses_template(self):
        plan = _make_plan(is_fallback=True, phase_count=2)
        summary = await PlanPresenter.to_summary(plan, language="zh")
        assert "2" in summary
        assert "LLM" in summary

    @pytest.mark.asyncio
    async def test_standard_summary_uses_template_in_english(self):
        plan = _make_plan(is_fallback=False, phase_count=3)
        summary = await PlanPresenter.to_summary(plan, language="en")
        assert "3" in summary
        assert "Analysis plan" in summary

    @pytest.mark.asyncio
    async def test_llm_summary_used_when_client_configured(self):
        class FakeLLM:
            def is_configured(self):
                return True

            async def chat_completion(self, **kwargs):
                return "Custom LLM summary"

        plan = _make_plan(is_fallback=False, phase_count=1)
        summary = await PlanPresenter.to_summary(plan, llm_client=FakeLLM())
        assert summary == "Custom LLM summary"

    @pytest.mark.asyncio
    async def test_llm_error_falls_back_to_template(self):
        class BrokenLLM:
            def is_configured(self):
                return True

            async def chat_completion(self, **kwargs):
                raise RuntimeError("LLM failure")

        plan = _make_plan(is_fallback=False, phase_count=2)
        summary = await PlanPresenter.to_summary(plan, language="en", llm_client=BrokenLLM())
        assert "2" in summary


class TestPlanPayload:
    def test_payload_includes_derivation_and_risk_level(self):
        plan = _make_plan(is_fallback=True, phase_count=1)
        plan.plan_result.derivation = "llm-fallback"
        plan.plan_result.risk_level = "high"
        plan.plan_result.approval_required = True
        plan.plan_result.phases[0].derivation = "llm-fallback"
        plan.plan_result.phases[0].risk_level = "high"

        payload = PlanPresenter.to_user_payload(plan)

        assert payload["derivation"] == "llm-fallback"
        assert payload["risk_level"] == "high"
        assert payload["approval_required"] is True
        assert payload["phases"][0]["derivation"] == "llm-fallback"
        assert payload["phases"][0]["risk_level"] == "high"

    def test_payload_includes_derivation_summary(self):
        plan = _make_plan(is_fallback=False, phase_count=1)
        plan.plan_result.phases[0].derivation = "domain-strategy"

        payload = PlanPresenter.to_user_payload(plan)

        assert payload["phases"][0]["derivation_summary"] == "来自领域策略模板"

    def test_payload_includes_anti_hallucination_meta(self):
        plan = _make_plan(is_fallback=False, phase_count=1)
        plan.plan_result.phases[0].derivation = "standalone-skill"
        plan.plan_result.phases[0].risk_level = "medium"
        plan.plan_result.phases[0].parameter_sources = {"resolution": "skill_default"}
        plan.plan_result.phases[0].parameters = {"resolution": 1.0}

        payload = PlanPresenter.to_user_payload(plan)

        meta = payload["phases"][0]["anti_hallucination_meta"]
        assert meta["skill_id"] == "scanpy_qc"
        assert meta["derivation"] == "standalone-skill"
        assert meta["risk_level"] == "medium"
        assert meta["parameter_sources"] == {"resolution": "skill_default"}
        assert meta["missing_required_inputs"] == []

    def test_payload_reports_missing_required_inputs(self):
        skill = SkillDefinition(
            id="gap_filling",
            name="Gap Filling",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                properties={"input_file": {"type": "string"}},
                required=["input_file"],
            ),
        )
        plan = _make_plan(is_fallback=False, phase_count=1)
        plan.plan_result.phases[0].selected_skill = skill
        plan.plan_result.phases[0].parameters = {}

        payload = PlanPresenter.to_user_payload(plan)

        meta = payload["phases"][0]["anti_hallucination_meta"]
        assert meta["missing_required_inputs"] == ["input_file"]
