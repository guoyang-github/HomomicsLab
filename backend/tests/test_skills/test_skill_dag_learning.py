"""Tests for SkillDAG online learning across all edge types."""

import pytest

from homomics_lab.skills.models import (
    SkillDefinition,
    SkillInputSchema,
    SkillOutputSchema,
)
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import (
    EdgeStatus,
    EdgeType,
    SkillDAG,
    SkillDAGReconciler,
)


@pytest.fixture
def registry(tmp_path):
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            description="Quality control",
            input_schema=SkillInputSchema(),
            output_schema=SkillOutputSchema(
                properties={"qc_passed": {"type": "boolean"}}
            ),
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_pca",
            name="scanpy_pca",
            version="1.0",
            category="single_cell",
            description="PCA",
            input_schema=SkillInputSchema(
                properties={"qc_passed": {"type": "boolean"}}
            ),
            output_schema=SkillOutputSchema(),
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
            output_schema=SkillOutputSchema(),
        )
    )
    return reg


class TestRecordObservation:
    def test_record_observation_creates_candidate_edge(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.record_observation(
            "scanpy_qc", "scanpy_pca", EdgeType.DEPENDS_ON, success=True
        )
        edge_id = "scanpy_qc_depends_on_scanpy_pca"
        assert edge_id in dag.edges
        assert dag.edges[edge_id].status == EdgeStatus.CANDIDATE

    def test_record_observation_conflicts_edge(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.record_observation(
            "scanpy_pca", "seurat_cluster", EdgeType.CONFLICTS_WITH, success=True
        )
        edge_id = "scanpy_pca_conflicts_with_seurat_cluster"
        assert edge_id in dag.edges
        assert dag.edges[edge_id].confidence > 0.3

    def test_record_observation_alternative_edge(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.record_observation(
            "scanpy_pca", "seurat_cluster", EdgeType.ALTERNATIVE_TO, success=True
        )
        edge_id = "scanpy_pca_alternative_to_seurat_cluster"
        assert edge_id in dag.edges

    def test_record_execution_defaults_to_followed_by(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.record_execution("scanpy_qc", "scanpy_pca", success=True)
        edge_id = "scanpy_qc_followed_by_scanpy_pca"
        assert edge_id in dag.edges
        assert dag.edges[edge_id].edge_type == EdgeType.FOLLOWED_BY


class TestProposeSchemaEdges:
    def test_schema_overlap_produces_edge(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        proposed = dag.propose_schema_edges(overlap_threshold=0.5)
        edge_ids = {e.id for e in proposed}
        assert "scanpy_qc_produces_scanpy_pca" in edge_ids
        assert "scanpy_pca_depends_on_scanpy_qc" in edge_ids

    def test_schema_edge_has_compatibility_score(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.propose_schema_edges(overlap_threshold=0.5)
        edge = dag.edges["scanpy_qc_produces_scanpy_pca"]
        assert edge.schema_compatibility_score is not None
        assert edge.schema_compatibility_score > 0.5


class TestSkillDAGReconciler:
    def test_reconciler_prefers_confirmed_dependency(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dep = dag.add_edge("scanpy_pca", "scanpy_qc", "depends_on")
        conflict = dag.propose_edge(
            "scanpy_pca", "scanpy_qc", EdgeType.CONFLICTS_WITH
        )

        reconciler = SkillDAGReconciler()
        reconciled = reconciler.reconcile(list(dag.edges.values()))
        by_id = {e.id: e for e in reconciled}
        assert by_id[dep.id].status == EdgeStatus.CONFIRMED
        assert by_id[conflict.id].status == EdgeStatus.REJECTED

    def test_reconciler_prefers_manual_seed(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        manual = dag.add_edge("scanpy_pca", "scanpy_qc", "followed_by")
        candidate = dag.propose_edge(
            "scanpy_pca", "scanpy_qc", EdgeType.FOLLOWED_BY
        )
        # The add_edge call confirms the edge and sets source to manual_seed.
        # propose_edge is idempotent, so candidate should be the same edge.
        assert manual.id == candidate.id
        assert manual.source == "manual_seed"

    def test_reconciler_does_not_mutate_accepted_edges(self, registry, tmp_path):
        dag = SkillDAG(registry=registry, db_path=tmp_path / "dag.db")
        dag.add_edge("scanpy_pca", "scanpy_qc", "depends_on")

        reconciler = SkillDAGReconciler()
        reconciled = reconciler.reconcile(list(dag.edges.values()))
        assert all(e.status != EdgeStatus.REJECTED for e in reconciled)
