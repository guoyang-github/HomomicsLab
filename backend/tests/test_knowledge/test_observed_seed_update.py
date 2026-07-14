"""Tests for observed seed self-update (G4).

Real successful runs should produce candidate ``source="observed"`` SkillDAG
edges. After ``seed_observed_promotion_threshold`` consecutive successes the
edge is promoted to CONFIRMED without touching hand-crafted ``source="seed"``
baselines.
"""

import pytest

from homomics_lab.knowledge.seed import (
    SEED_EDGE_SUCCESSES,
    record_observed_seed_edges,
    seed_baselines,
)
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import EdgeStatus, EdgeType, SkillDAG

SMALL_SEED_DATA = {
    "experiments": [],
    "experiment_edges": [],
    "skill_edges": [
        {
            "from": "scanpy_qc",
            "to": "scanpy_pca",
            "edge_type": "followed_by",
            "context": "test seed edge",
        },
    ],
}


@pytest.fixture
def dag(tmp_path):
    return SkillDAG(registry=SkillRegistry(), db_path=tmp_path / "skill_dag.db")


class TestObservedSeedPromotion:
    def test_single_successful_run_creates_candidate(self, dag):
        dag.record_observation(
            "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
        )
        report = record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=3)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert report["pairs_evaluated"] == 1
        assert report["promoted"] == []
        assert edge.status == EdgeStatus.CANDIDATE
        assert edge.consecutive_success_count == 1
        assert edge.source == "runtime_proposal"

    def test_promotes_after_threshold_consecutive_successes(self, dag):
        threshold = 3
        for _ in range(threshold):
            dag.record_observation(
                "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
            )
            record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=threshold)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.status == EdgeStatus.CONFIRMED
        assert edge.source == "observed"
        assert edge.confidence == 1.0
        assert edge.failure_count == 0
        assert edge.consecutive_success_count == threshold

    def test_failure_resets_consecutive_count_and_blocks_promotion(self, dag):
        threshold = 3
        # Two successes, one failure, two successes: should not promote.
        for _ in range(2):
            dag.record_observation(
                "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
            )
            record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=threshold)

        dag.record_observation(
            "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=False
        )
        record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=threshold)

        for _ in range(2):
            dag.record_observation(
                "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
            )
            record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=threshold)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.status == EdgeStatus.CANDIDATE
        assert edge.consecutive_success_count == 2
        assert edge.failure_count == 1
        assert edge.source == "runtime_proposal"

    def test_failure_after_promotion_does_not_retag_seed(self, dag):
        threshold = 3
        for _ in range(threshold):
            dag.record_observation(
                "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
            )
            record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=threshold)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.status == EdgeStatus.CONFIRMED
        assert edge.source == "observed"

        # A later failure should be recorded but must not retag the edge as seed.
        dag.record_observation(
            "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=False
        )
        assert edge.source == "observed"

    def test_does_not_pollute_manual_seed_edge(self, dag):
        manual = dag.add_edge("scanpy_qc", "scanpy_pca", "followed_by", context="manual")
        assert manual.source == "manual_seed"
        assert manual.status == EdgeStatus.CONFIRMED

        for _ in range(5):
            dag.record_observation(
                "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
            )
            record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=3)

        assert manual.source == "manual_seed"
        assert manual.status == EdgeStatus.CONFIRMED

    def test_does_not_pollute_yaml_seed_edge(self, tmp_path):
        from homomics_lab.knowledge.cbkb import CBKB

        cbkb = CBKB(base_dir=tmp_path / "cbkb")
        dag = SkillDAG(registry=SkillRegistry(), db_path=tmp_path / "skill_dag.db")
        seed_baselines(cbkb, dag, data=SMALL_SEED_DATA)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.source == "seed"
        assert edge.proposed_by == "seed"
        assert edge.status == EdgeStatus.CONFIRMED
        assert edge.success_count == SEED_EDGE_SUCCESSES

        for _ in range(5):
            dag.record_observation(
                "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
            )
            record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=3)

        assert edge.source == "seed"
        assert edge.status == EdgeStatus.CONFIRMED

    def test_promotion_threshold_configurable(self, dag):
        threshold = 2
        for _ in range(threshold):
            dag.record_observation(
                "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=True
            )
            record_observed_seed_edges(dag, [("scanpy_qc", "scanpy_pca")], threshold=threshold)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert edge.status == EdgeStatus.CONFIRMED
        assert edge.source == "observed"

    def test_multiple_pairs_in_same_run(self, dag):
        threshold = 2
        pairs = [("scanpy_qc", "scanpy_pca"), ("scanpy_pca", "scanpy_cluster")]
        for _ in range(threshold):
            for a, b in pairs:
                dag.record_observation(a, b, EdgeType.FOLLOWED_BY, success=True)
            report = record_observed_seed_edges(dag, pairs, threshold=threshold)

        assert set(report["promoted"]) == {
            "scanpy_qc_followed_by_scanpy_pca",
            "scanpy_pca_followed_by_scanpy_cluster",
        }
        assert dag.edges["scanpy_qc_followed_by_scanpy_pca"].source == "observed"
        assert dag.edges["scanpy_pca_followed_by_scanpy_cluster"].source == "observed"

    def test_failed_pair_is_not_evaluated_for_promotion(self, dag):
        dag.record_observation(
            "scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY, success=False
        )
        report = record_observed_seed_edges(dag, [], threshold=3)

        edge = dag.edges["scanpy_qc_followed_by_scanpy_pca"]
        assert report["pairs_evaluated"] == 0
        assert report["promoted"] == []
        assert edge.status == EdgeStatus.CANDIDATE
        assert edge.consecutive_success_count == 0
