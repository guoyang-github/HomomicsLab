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
