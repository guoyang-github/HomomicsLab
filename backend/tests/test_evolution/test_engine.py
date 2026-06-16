"""Tests for the EvolutionEngine orchestrator."""

import pytest

from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.evolution.engine import EvolutionEngine
from homomics_lab.knowledge.cbkb import CBKB, ExperimentNode
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG


@pytest.fixture
def evolution_setup(tmp_path):
    reg = SkillRegistry()
    for sid in ("scanpy_qc", "scanpy_normalize"):
        reg.register(
            SkillDefinition(
                id=sid,
                name=sid,
                version="1.0",
                category="single_cell",
                input_schema=SkillInputSchema(),
            )
        )
    cbkb = CBKB(base_dir=tmp_path / "cbkb")
    dag = SkillDAG(registry=reg, db_path=tmp_path / "dag.db")
    plan_engine = PlanEngine(skill_registry=reg, skill_dag=dag, cbkb=cbkb)
    engine = EvolutionEngine(cbkb=cbkb, skill_dag=dag, plan_engine=plan_engine)
    return engine, cbkb, dag, reg


_node_counter = 0


def _add_node(cbkb, skills, success=True):
    global _node_counter
    _node_counter += 1
    node = ExperimentNode(
        bundle_id=f"bundle_{_node_counter:04d}",
        project_id="proj_evolution",
        created_at="2026-01-01T00:00:00+00:00",
        skills_used=skills,
        phases=skills,
        summary="test",
        metadata={"success": success, "strategy_type": "single_cell"},
    )
    cbkb.add_experiment_node(node)


class TestEvolutionEngine:
    def test_run_evolution_pass_returns_report(self, evolution_setup):
        engine, cbkb, dag, reg = evolution_setup
        for _ in range(6):
            _add_node(cbkb, ["scanpy_qc", "scanpy_normalize"], success=True)

        report = engine.run_evolution_pass()

        assert report.timestamp is not None
        assert report.skill_dag_changes["experiment_nodes_processed"] == 6
        assert report.skill_dag_changes["transitions_recorded"] == 6
        edge = dag.edges.get("scanpy_qc_followed_by_scanpy_normalize")
        assert edge is not None
        assert edge.execution_count == 6

    def test_evolution_pass_does_not_raise_on_empty_cbkb(self, evolution_setup):
        engine, _, _, _ = evolution_setup
        report = engine.run_evolution_pass()
        assert report.skill_dag_changes["experiment_nodes_processed"] == 0
        assert report.errors == []

    def test_evolution_pass_applies_sop(self, evolution_setup):
        engine, cbkb, dag, reg = evolution_setup
        # Add enough successful identical workflows to trigger an auto-SOP.
        for i in range(5):
            node = ExperimentNode(
                bundle_id=f"sop_bundle_{i}",
                project_id="proj_evolution",
                created_at="2026-01-01T00:00:00+00:00",
                skills_used=["scanpy_qc", "scanpy_normalize"],
                phases=["scanpy_qc", "scanpy_normalize"],
                summary="test",
                metadata={"success": True, "strategy_type": "single_cell"},
            )
            cbkb.add_experiment_node(node)

        report = engine.run_evolution_pass(sop_confidence_threshold=0.5)

        assert report.sop_proposals >= 1
        assert report.sops_applied >= 1
        sops = cbkb.list_sops()
        assert any(sop.id.startswith("sop_proposal_") for sop in sops)

    def test_evolution_report_serializable(self, evolution_setup):
        engine, _, _, _ = evolution_setup
        report = engine.run_evolution_pass()
        data = report.to_dict()
        assert "skill_dag_changes" in data
        assert isinstance(data["parameter_preferences"], int)
