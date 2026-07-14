"""Tests for cold-start baseline seeding (knowledge/seed.py, P2-2)."""

from pathlib import Path

import pytest

from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.knowledge.seed import (
    DEFAULT_SEED_PATH,
    SEED_EDGE_SUCCESSES,
    is_store_empty,
    load_seed_data,
    seed_baselines,
)
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import EdgeStatus, SkillDAG

SMALL_SEED_DATA = {
    "experiments": [
        {
            "bundle_id": "seed_test_scrnaseq",
            "project_id": "system",
            "created_at": "2024-01-01T00:00:00+00:00",
            "skills_used": ["scanpy_qc", "scanpy_pca", "scanpy_cluster"],
            "phases": ["qc", "pca", "clustering"],
            "summary": "Small test seed experiment",
            "metadata": {"source": "seed", "dataset": "test_dataset"},
        },
        {
            "bundle_id": "seed_test_spatial",
            "project_id": "system",
            "created_at": "2024-01-01T00:00:00+00:00",
            "skills_used": ["spatial_qc", "spatial_domains"],
            "phases": ["qc", "domains"],
            "summary": "Small test spatial seed experiment",
            "metadata": {"source": "seed", "dataset": "test_spatial"},
        },
    ],
    "experiment_edges": [
        {
            "from_bundle": "seed_test_scrnaseq",
            "to_bundle": "seed_test_spatial",
            "edge_type": "shares_skill",
            "strength": 0.5,
        },
    ],
    "skill_edges": [
        {
            "from": "scanpy_qc",
            "to": "scanpy_pca",
            "edge_type": "followed_by",
            "context": "test edge",
        },
        {
            "from": "scanpy_pca",
            "to": "scanpy_cluster",
            "edge_type": "followed_by",
            "context": "test edge",
        },
    ],
}


@pytest.fixture
def stores(tmp_path):
    cbkb = CBKB(base_dir=tmp_path / "cbkb")
    dag = SkillDAG(registry=SkillRegistry(), db_path=tmp_path / "skill_dag.db")
    return cbkb, dag


class TestSeedBaselines:
    def test_first_seed_populates_stores(self, stores):
        cbkb, dag = stores
        report = seed_baselines(cbkb, dag, data=SMALL_SEED_DATA)

        assert report["experiments_added"] == 2
        assert report["experiment_edges_added"] == 1
        assert report["skill_edges_confirmed"] == 2
        assert report["skipped"] == 0

        node = cbkb.get_experiment_node("seed_test_scrnaseq")
        assert node is not None
        assert node.project_id == "system"
        assert node.metadata["source"] == "seed"
        assert node.skills_used == ["scanpy_qc", "scanpy_pca", "scanpy_cluster"]
        assert cbkb.list_experiment_nodes_by_project("system", limit=10)

        related = cbkb.find_related_experiments("seed_test_scrnaseq", "shares_skill")
        assert [r[0] for r in related] == ["seed_test_spatial"]

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.status == EdgeStatus.CONFIRMED
        assert edge.proposed_by == "seed"
        assert edge.execution_count == SEED_EDGE_SUCCESSES
        assert edge.success_count == SEED_EDGE_SUCCESSES

    def test_seed_is_idempotent(self, stores):
        cbkb, dag = stores
        first = seed_baselines(cbkb, dag, data=SMALL_SEED_DATA)
        second = seed_baselines(cbkb, dag, data=SMALL_SEED_DATA)

        assert second["experiments_added"] == 0
        assert second["experiment_edges_added"] == 0
        assert second["skill_edges_confirmed"] == 0
        assert second["skipped"] == (
            first["experiments_added"]
            + first["experiment_edges_added"]
            + first["skill_edges_confirmed"]
        )

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.execution_count == SEED_EDGE_SUCCESSES
        assert len(cbkb.list_experiment_nodes_by_project("system", limit=100)) == 2

    def test_force_reseeds(self, stores):
        cbkb, dag = stores
        seed_baselines(cbkb, dag, data=SMALL_SEED_DATA)
        report = seed_baselines(cbkb, dag, data=SMALL_SEED_DATA, force=True)

        assert report["experiments_added"] == 2
        assert report["experiment_edges_added"] == 1
        assert report["skill_edges_confirmed"] == 2
        assert report["skipped"] == 0

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.execution_count == 2 * SEED_EDGE_SUCCESSES
        # INSERT OR REPLACE keeps a single node per bundle_id.
        assert len(cbkb.list_experiment_nodes_by_project("system", limit=100)) == 2

    def test_missing_seed_metadata_defaults(self, stores):
        cbkb, dag = stores
        data = {
            "experiments": [
                {
                    "bundle_id": "seed_minimal",
                    "skills_used": ["scanpy_qc"],
                    "phases": ["qc"],
                }
            ]
        }
        seed_baselines(cbkb, dag, data=data)
        node = cbkb.get_experiment_node("seed_minimal")
        assert node.project_id == "system"
        assert node.metadata["source"] == "seed"


class TestIsStoreEmpty:
    def test_empty_stores(self, stores):
        cbkb, dag = stores
        assert is_store_empty(cbkb, dag) is True

    def test_not_empty_after_seed(self, stores):
        cbkb, dag = stores
        seed_baselines(cbkb, dag, data=SMALL_SEED_DATA)
        assert is_store_empty(cbkb, dag) is False

    def test_not_empty_with_real_project_experiment(self, stores):
        from homomics_lab.knowledge.cbkb import ExperimentNode

        cbkb, dag = stores
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="real_bundle_1",
                project_id="user_project",
                created_at="2024-01-01T00:00:00+00:00",
                skills_used=["scanpy_qc"],
                phases=["qc"],
            )
        )
        assert is_store_empty(cbkb, dag) is False

    def test_not_empty_with_confirmed_non_seed_edge(self, stores):
        cbkb, dag = stores
        dag.add_edge("scanpy_qc", "scanpy_pca", "followed_by", context="manual")
        assert is_store_empty(cbkb, dag) is False


class TestBundledSeedData:
    def test_load_bundled_seed_data(self):
        data = load_seed_data()
        assert len(data["experiments"]) >= 2
        assert len(data["skill_edges"]) >= 6

    def test_bundled_data_isolation_tags(self):
        data = load_seed_data()
        for exp in data["experiments"]:
            assert exp["bundle_id"].startswith("seed_")
            assert exp["project_id"] == "system"
            assert exp["metadata"]["source"] == "seed"
            assert "dataset" in exp["metadata"]

    def test_bundled_skill_ids_exist(self):
        """Every skill id referenced in the seed data must be a real skill."""
        repo_root = Path(__file__).resolve().parents[3]
        skills_dir = repo_root / "skills"
        real_skill_ids = {p.name for p in skills_dir.iterdir() if p.is_dir()}
        assert real_skill_ids, "repo skills/ directory not found"

        data = load_seed_data()
        referenced = set()
        for edge in data["skill_edges"]:
            referenced.add(edge["from"])
            referenced.add(edge["to"])
        for exp in data["experiments"]:
            referenced.update(exp["skills_used"])
        unknown = referenced - real_skill_ids
        assert not unknown, f"seed data references unknown skill ids: {unknown}"

    def test_bundled_experiment_skills_match_skill_edges(self):
        """Seeded edges should stay within the seeded experiments' skill sets."""
        data = load_seed_data()
        known = set()
        for exp in data["experiments"]:
            known.update(exp["skills_used"])
        for edge in data["skill_edges"]:
            assert edge["from"] in known
            assert edge["to"] in known

    def test_seed_with_bundled_data(self, stores):
        cbkb, dag = stores
        report = seed_baselines(cbkb, dag)
        assert report["experiments_added"] >= 2
        assert report["skill_edges_confirmed"] >= 6
        assert not is_store_empty(cbkb, dag)
        # Re-run is fully idempotent.
        second = seed_baselines(cbkb, dag)
        assert second["experiments_added"] == 0
        assert second["skill_edges_confirmed"] == 0

    def test_default_seed_path_exists(self):
        assert DEFAULT_SEED_PATH.exists()
