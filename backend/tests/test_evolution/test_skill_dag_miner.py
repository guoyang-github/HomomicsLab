"""Tests for SkillDAG edge mining from CBKB history."""

import pytest

from homomics_lab.evolution.skill_dag_miner import SkillDAGMiner
from homomics_lab.knowledge.cbkb import CBKB, ExperimentNode
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import EdgeStatus, SkillDAG


@pytest.fixture
def skill_registry():
    reg = SkillRegistry()
    for sid in ("scanpy_qc", "scanpy_normalize", "scanpy_pca"):
        reg.register(
            SkillDefinition(
                id=sid,
                name=sid,
                version="1.0",
                category="single_cell",
                input_schema=SkillInputSchema(),
            )
        )
    return reg


@pytest.fixture
def miner(skill_registry, tmp_path):
    cbkb = CBKB(base_dir=tmp_path / "cbkb")
    skill_dag = SkillDAG(registry=skill_registry, db_path=tmp_path / "dag.db")
    return SkillDAGMiner(cbkb, skill_dag), cbkb, skill_dag


_node_counter = 0


def _add_node(cbkb, project_id, skills, success=True):
    global _node_counter
    _node_counter += 1
    node = ExperimentNode(
        bundle_id=f"bundle_{_node_counter:04d}",
        project_id=project_id,
        created_at="2026-01-01T00:00:00+00:00",
        skills_used=skills,
        phases=skills,
        summary="test",
        metadata={"success": success},
    )
    cbkb.add_experiment_node(node)


class TestSkillDAGMiner:
    def test_mine_records_execution_transitions(self, miner):
        m, cbkb, dag = miner
        for _ in range(3):
            _add_node(cbkb, "p1", ["scanpy_qc", "scanpy_normalize"])

        summary = m.mine_edges(min_cooccurrence=1)

        assert summary["experiment_nodes_processed"] == 3
        assert summary["transitions_recorded"] == 3
        edge = dag.edges.get("scanpy_qc_followed_by_scanpy_normalize")
        assert edge is not None
        assert edge.execution_count >= 3

    def test_mine_confirms_edge_after_threshold(self, miner):
        m, cbkb, dag = miner
        for _ in range(6):
            _add_node(cbkb, "p1", ["scanpy_qc", "scanpy_normalize"], success=True)

        m.mine_edges(min_cooccurrence=1)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_normalize"]
        # SkillDAG._transition_status requires >=5 executions and >=80% success.
        assert edge.status == EdgeStatus.CONFIRMED
        assert edge.confidence >= 0.7

    def test_mine_records_infrequent_transition_as_candidate(self, miner):
        m, cbkb, dag = miner
        for _ in range(2):
            _add_node(cbkb, "p1", ["scanpy_normalize", "scanpy_pca"], success=True)

        # min_cooccurrence=3 means infer_from_history will not promote, but
        # record_execution should still create a runtime proposal edge.
        summary = m.mine_edges(min_cooccurrence=3)

        assert summary["transitions_recorded"] == 2
        edge = dag.edges.get("scanpy_normalize_followed_by_scanpy_pca")
        assert edge is not None
        assert edge.status.value == "candidate"

    def test_mine_logs_transitions(self, miner):
        m, cbkb, dag = miner
        for _ in range(6):
            _add_node(cbkb, "p1", ["scanpy_qc", "scanpy_normalize"], success=True)

        m.mine_edges(min_cooccurrence=1)

        logs = cbkb.get_skill_evolution()
        assert any(
            rec.from_skill == "scanpy_qc" and rec.to_skill == "scanpy_normalize"
            for rec in logs
        )
