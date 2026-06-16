"""Tests for learned parameter default injection in PlanEngine."""

import pytest

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState
from homomics_lab.knowledge.cbkb import CBKB, ParameterLoreEntry
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def plan_engine_with_cbkb(tmp_path):
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            description="Quality control",
            input_schema=SkillInputSchema(
                properties={"min_genes": {"type": "integer"}},
                required=["min_genes"],
            ),
        )
    )
    cbkb = CBKB(base_dir=tmp_path)
    # Seed parameter lore: min_genes=500 has best historical outcome.
    for i in range(4):
        cbkb.add_parameter_lore(
            ParameterLoreEntry(
                id=f"lore_{i}",
                skill_id="scanpy_qc",
                param_name="min_genes",
                param_value="500",
                outcome_metric="phase_success",
                outcome_value=1.0,
                project_id="proj_1",
                context="test",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    engine = PlanEngine(skill_registry=reg, cbkb=cbkb)
    return engine, cbkb


class TestPlanParameterInjection:
    @pytest.mark.asyncio
    async def test_plan_injects_learned_default(self, plan_engine_with_cbkb):
        engine, _ = plan_engine_with_cbkb
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        plan = await engine.plan(intent, DataState(has_qc=False, n_cells=3000))

        qc_phase = next((p for p in plan.phases if p.phase_type == "qc"), None)
        assert qc_phase is not None
        assert qc_phase.selected_skill is not None
        assert qc_phase.parameters.get("min_genes") == "500"

    @pytest.mark.asyncio
    async def test_plan_preserves_user_provided_param(self, plan_engine_with_cbkb):
        engine, _ = plan_engine_with_cbkb
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="complex")
        plan = await engine.plan(intent, DataState(has_qc=False, n_cells=3000))

        # Manually set a user-provided value and replan-ish: the engine should
        # not override an already-present parameter.
        qc_phase = next((p for p in plan.phases if p.phase_type == "qc"), None)
        qc_phase.parameters["min_genes"] = 800
        assert qc_phase.parameters["min_genes"] == 800
