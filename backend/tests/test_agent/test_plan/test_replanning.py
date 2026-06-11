"""Tests for DynamicReplanningEngine."""

import pytest

from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.replanning import (
    DynamicReplanningEngine,
    PlanDelta,
    ReplanningTrigger,
)
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


class MockSkillDAG:
    """Lightweight mock of SkillDAG for unit testing."""

    def __init__(self, registry):
        self.registry = registry
        self._alternatives: dict = {}

    def add_alternative(self, from_skill: str, to_skill: str, confidence: float = 0.9) -> None:
        self._alternatives.setdefault(from_skill, []).append((to_skill, confidence))

    def get_alternatives(self, skill_id: str):
        alts = self._alternatives.get(skill_id, [])
        return sorted(alts, key=lambda x: x[1], reverse=True)


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
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="seurat_qc",
            name="seurat_qc",
            version="1.0",
            category="single_cell",
            description="Seurat QC alternative",
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_cluster",
            name="scanpy_cluster",
            version="1.0",
            category="single_cell",
            description="Clustering",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.fixture
def mock_skill_dag(registry):
    dag = MockSkillDAG(registry)
    dag.add_alternative("scanpy_qc", "seurat_qc", confidence=0.95)
    return dag


@pytest.fixture
def plan_engine(registry):
    return PlanEngine(skill_registry=registry)


@pytest.fixture
def base_plan():
    """A typical single-cell plan for replanning tests."""
    return PlanResult(
        phases=[
            Phase(phase_type="qc", required=True, selected_skill=None, parameters={"min_genes": 200}),
            Phase(phase_type="normalization", required=True, selected_skill=None, parameters={}),
            Phase(phase_type="dim_reduction", required=True, selected_skill=None, parameters={"n_pcs": 30}),
            Phase(phase_type="clustering", required=True, selected_skill=None, parameters={}),
            Phase(phase_type="differential_expression", required=True, selected_skill=None, parameters={"method": "wilcoxon"}),
            Phase(phase_type="visualization", required=False, selected_skill=None, parameters={}),
        ],
        strategy_name="single_cell_standard",
        data_state=DataState(),
    )


class TestDynamicReplanningEngine:
    def test_anomaly_critical_qc_inserts_re_qc(self, plan_engine, mock_skill_dag, base_plan):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        trigger = ReplanningTrigger(
            trigger_type="anomaly_detected",
            severity="critical",
            context={"phase_type": "qc"},
        )

        new_plan = engine.replan(base_plan, [trigger], DataState())

        phase_types = [p.phase_type for p in new_plan.phases]
        assert phase_types.count("qc") == 2
        re_qc_idx = phase_types.index("qc") + 1
        assert phase_types[re_qc_idx] == "qc"
        assert new_plan.phases[re_qc_idx].parameters.get("tight_mode") is True
        assert new_plan.reproducibility_context.get("replanned") is True

    def test_anomaly_non_critical_does_nothing(self, plan_engine, mock_skill_dag, base_plan):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        trigger = ReplanningTrigger(
            trigger_type="anomaly_detected",
            severity="major",
            context={"phase_type": "qc"},
        )

        new_plan = engine.replan(base_plan, [trigger], DataState())

        assert len(new_plan.phases) == len(base_plan.phases)
        assert new_plan.reproducibility_context["replanning_delta"]["phases_inserted"] == 0

    def test_batch_effect_inserts_integration(self, plan_engine, mock_skill_dag, base_plan):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        trigger = ReplanningTrigger(
            trigger_type="data_state_changed",
            severity="major",
            context={"change_type": "batch_effect"},
        )

        new_plan = engine.replan(base_plan, [trigger], DataState())

        phase_types = [p.phase_type for p in new_plan.phases]
        assert "integration" in phase_types
        de_idx = phase_types.index("differential_expression")
        assert phase_types[de_idx - 1] == "integration"

    def test_data_state_changed_non_batch_effect_does_nothing(self, plan_engine, mock_skill_dag, base_plan):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        trigger = ReplanningTrigger(
            trigger_type="data_state_changed",
            severity="minor",
            context={"change_type": "new_samples_added"},
        )

        new_plan = engine.replan(base_plan, [trigger], DataState())

        assert len(new_plan.phases) == len(base_plan.phases)

    def test_skill_failure_swaps_skill(self, plan_engine, registry, mock_skill_dag, base_plan):
        # Assign a skill that will "fail"
        base_plan.phases[0].selected_skill = registry.get("scanpy_qc")
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        trigger = ReplanningTrigger(
            trigger_type="skill_failure",
            severity="critical",
            context={"failed_skill_id": "scanpy_qc"},
        )

        new_plan = engine.replan(base_plan, [trigger], DataState())

        assert new_plan.phases[0].selected_skill.id == "seurat_qc"
        assert "seurat_qc" in new_plan.reproducibility_context["replanning_delta"]["reason"]

    def test_skill_failure_no_alternative(self, plan_engine, registry, base_plan):
        # No skill_dag provided → no alternatives
        base_plan.phases[0].selected_skill = registry.get("scanpy_qc")
        engine = DynamicReplanningEngine(plan_engine, skill_dag=None)
        trigger = ReplanningTrigger(
            trigger_type="skill_failure",
            severity="critical",
            context={"failed_skill_id": "scanpy_qc"},
        )

        new_plan = engine.replan(base_plan, [trigger], DataState())

        # Skill should remain unchanged
        assert new_plan.phases[0].selected_skill.id == "scanpy_qc"
        assert "No alternative found" in new_plan.reproducibility_context["replanning_delta"]["reason"]

    def test_user_intervention_propagates_params(self, plan_engine, mock_skill_dag, base_plan):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        trigger = ReplanningTrigger(
            trigger_type="user_intervention",
            severity="minor",
            context={
                "phase_type": "dim_reduction",
                "new_params": {"n_pcs": 50},
                "propagate_keys": ["n_pcs"],
            },
        )
        # Set n_pcs in a downstream phase so propagation has something to update
        base_plan.phases[4].parameters["n_pcs"] = 30

        new_plan = engine.replan(base_plan, [trigger], DataState())

        dim_reduction_phase = next(p for p in new_plan.phases if p.phase_type == "dim_reduction")
        assert dim_reduction_phase.parameters["n_pcs"] == 50

        de_phase = next(p for p in new_plan.phases if p.phase_type == "differential_expression")
        assert de_phase.parameters["n_pcs"] == 50

    def test_user_intervention_no_propagate_keys(self, plan_engine, mock_skill_dag, base_plan):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        trigger = ReplanningTrigger(
            trigger_type="user_intervention",
            severity="minor",
            context={
                "phase_type": "qc",
                "new_params": {"min_genes": 500},
            },
        )

        new_plan = engine.replan(base_plan, [trigger], DataState())

        qc_phase = next(p for p in new_plan.phases if p.phase_type == "qc")
        assert qc_phase.parameters["min_genes"] == 500
        # No downstream propagation because no matching keys in other phases

    def test_multiple_triggers_combined(self, plan_engine, registry, mock_skill_dag, base_plan):
        base_plan.phases[0].selected_skill = registry.get("scanpy_qc")
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        triggers = [
            ReplanningTrigger(
                trigger_type="anomaly_detected",
                severity="critical",
                context={"phase_type": "qc"},
            ),
            ReplanningTrigger(
                trigger_type="skill_failure",
                severity="critical",
                context={"failed_skill_id": "scanpy_qc"},
            ),
            ReplanningTrigger(
                trigger_type="data_state_changed",
                severity="major",
                context={"change_type": "batch_effect"},
            ),
        ]

        new_plan = engine.replan(base_plan, triggers, DataState())

        phase_types = [p.phase_type for p in new_plan.phases]
        # Re-QC inserted after QC
        assert phase_types.count("qc") == 2
        # Integration inserted before DE
        assert "integration" in phase_types
        # Skill swapped
        assert new_plan.phases[0].selected_skill.id == "seurat_qc"
        assert new_plan.reproducibility_context["replanning_delta"]["phases_inserted"] == 2

    def test_replanning_trigger_validation(self):
        with pytest.raises(ValueError, match="Invalid trigger_type"):
            ReplanningTrigger(trigger_type="unknown_trigger")

        with pytest.raises(ValueError, match="Invalid severity"):
            ReplanningTrigger(trigger_type="anomaly_detected", severity="extreme")

    def test_insert_and_remove_phase_helpers(self, plan_engine, mock_skill_dag, base_plan):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        new_phase = Phase(phase_type="extra", required=True)

        engine._insert_phase(base_plan, 1, new_phase)
        assert base_plan.phases[1].phase_type == "extra"
        assert len(base_plan.phases) == 7

        engine._remove_phase(base_plan, 1)
        assert base_plan.phases[1].phase_type != "extra"
        assert len(base_plan.phases) == 6

    def test_find_alternative_skill(self, plan_engine, mock_skill_dag):
        engine = DynamicReplanningEngine(plan_engine, mock_skill_dag)
        alt = engine._find_alternative_skill("scanpy_qc")
        assert alt == "seurat_qc"

    def test_find_alternative_skill_no_dag(self, plan_engine):
        engine = DynamicReplanningEngine(plan_engine, skill_dag=None)
        alt = engine._find_alternative_skill("scanpy_qc")
        assert alt is None
