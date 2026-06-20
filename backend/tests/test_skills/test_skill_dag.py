"""Tests for SkillDAG."""


import pytest

from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import (
    EdgeStatus,
    EdgeType,
    SkillDAG,
)


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
            id="scanpy_pca",
            name="scanpy_pca",
            version="1.0",
            category="single_cell",
            description="PCA",
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
    reg.register(
        SkillDefinition(
            id="seurat_cluster",
            name="seurat_cluster",
            version="1.0",
            category="single_cell",
            description="Seurat clustering",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


class TestSkillDAGCore:
    def test_propose_edge_creates_candidate(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        edge = dag.propose_edge("scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY)
        assert edge.status == EdgeStatus.CANDIDATE
        assert edge.confidence == 0.3
        assert edge.source == "runtime_proposal"

    def test_propose_edge_idempotent(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        e1 = dag.propose_edge("scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY)
        e2 = dag.propose_edge("scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY)
        assert e1.id == e2.id

    def test_record_execution_proposes_edge(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.record_execution("scanpy_qc", "scanpy_pca", success=True)

        edge_id = "scanpy_qc_followed_by_scanpy_pca"
        assert edge_id in dag.edges
        assert dag.edges[edge_id].execution_count == 1
        assert dag.edges[edge_id].success_count == 1

    def test_record_execution_bumps_confidence(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        for _ in range(5):
            dag.record_execution("scanpy_qc", "scanpy_pca", success=True)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.confidence > 0.3

    def test_record_execution_failure_drops_confidence(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.record_execution("scanpy_qc", "scanpy_pca", success=False)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.confidence < 0.3

    def test_candidate_to_confirmed_transition(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        for _ in range(5):
            dag.record_execution("scanpy_qc", "scanpy_pca", success=True)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.status == EdgeStatus.CONFIRMED

    def test_confirmed_to_deprecated_transition(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        # First confirm it
        for _ in range(5):
            dag.record_execution("scanpy_qc", "scanpy_pca", success=True)

        # Then fail repeatedly
        for _ in range(10):
            dag.record_execution("scanpy_qc", "scanpy_pca", success=False)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.status == EdgeStatus.DEPRECATED

    def test_get_conflicts(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.propose_edge("scanpy_cluster", "seurat_cluster", EdgeType.CONFLICTS_WITH)
        dag.edges["scanpy_cluster_conflicts_with_seurat_cluster"].status = EdgeStatus.CONFIRMED
        dag.edges["scanpy_cluster_conflicts_with_seurat_cluster"].confidence = 1.0

        conflicts = dag.get_conflicts("scanpy_cluster")
        assert "seurat_cluster" in conflicts

    def test_get_followed_by(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.propose_edge("scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY)
        dag.edges["scanpy_qc_followed_by_scanpy_pca"].status = EdgeStatus.CONFIRMED
        dag.edges["scanpy_qc_followed_by_scanpy_pca"].confidence = 0.9

        followed = dag.get_followed_by("scanpy_qc")
        assert len(followed) == 1
        assert followed[0][0] == "scanpy_pca"

    def test_validate_sequence_no_conflicts(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        result = dag.validate_sequence(["scanpy_qc", "scanpy_pca", "scanpy_cluster"])
        assert result.valid is True

    def test_validate_sequence_detects_conflict(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.propose_edge("scanpy_cluster", "seurat_cluster", EdgeType.CONFLICTS_WITH)
        dag.edges["scanpy_cluster_conflicts_with_seurat_cluster"].status = EdgeStatus.CONFIRMED
        dag.edges["scanpy_cluster_conflicts_with_seurat_cluster"].confidence = 1.0

        result = dag.validate_sequence(["scanpy_cluster", "seurat_cluster"])
        assert result.valid is False
        assert len(result.errors) == 1
        assert "Conflict" in result.errors[0]

    def test_infer_from_history(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        records = [
            {"skill_sequence": ["scanpy_qc", "scanpy_pca"]},
            {"skill_sequence": ["scanpy_qc", "scanpy_pca"]},
            {"skill_sequence": ["scanpy_qc", "scanpy_pca"]},
        ]
        inferred = dag.infer_from_history(records, min_cooccurrence=3)
        assert len(inferred) == 1
        assert inferred[0].from_skill == "scanpy_qc"
        assert inferred[0].to_skill == "scanpy_pca"

    def test_persistence_roundtrip(self, registry, tmp_path):
        db_path = tmp_path / "dag.db"
        dag1 = SkillDAG(registry=registry, db_path=db_path)
        dag1.propose_edge("scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY)

        # Create new instance with same DB
        dag2 = SkillDAG(registry=registry, db_path=db_path)
        assert "scanpy_qc_followed_by_scanpy_pca" in dag2.edges


class TestSkillDAGWithSeeds:
    def test_manual_seed_loading(self, registry, tmp_path):
        seed_file = tmp_path / "seeds.yaml"
        seed_file.write_text(
            """
version: "0.3.0"
seeds:
  - from: scanpy_qc
    to: scanpy_pca
    type: followed_by
    context: "test seed"
"""
        )
        dag = SkillDAG(
            registry=registry,
            db_path=tmp_path / "dag.db",
            manual_seed_path=seed_file,
        )
        edge = dag.edges.get("scanpy_qc_followed_by_scanpy_pca")
        assert edge is not None
        assert edge.status == EdgeStatus.CONFIRMED
        assert edge.confidence == 1.0
        assert edge.source == "manual_seed"
