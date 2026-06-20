"""Tests for CBKBCurator."""

import pytest

from homomics_lab.knowledge.cbkb import (
    AnomalyRecord,
    CBKB,
    ExperimentNode,
    LabSOP,
    ParameterLoreEntry,
)
from datetime import datetime, timezone

from homomics_lab.knowledge.curator import (
    CBKBCurator,
    NarrativeReport,
    TopicCluster,
)


@pytest.fixture
def cbkb(tmp_path):
    return CBKB(base_dir=tmp_path)


@pytest.fixture
def curator(cbkb):
    return CBKBCurator(cbkb=cbkb)


class TestDistillNewBundles:
    def test_empty_returns_empty(self, curator):
        assert curator.distill_new_bundles() == []

    def test_skill_sequence_insight(self, curator, cbkb):
        for i in range(3):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id="p1",
                    created_at="2024-06-01T00:00:00+00:00",
                    skills_used=["scanpy_qc", "scanpy_pca"],
                    phases=["qc", "pca"],
                    summary="test",
                )
            )
        insights = curator.distill_new_bundles()
        assert any(i.insight_type == "skill_sequence" for i in insights)

    def test_parameter_combo_insight(self, curator, cbkb):
        cbkb.add_parameter_lore(
            ParameterLoreEntry(
                id="pl1",
                skill_id="s1",
                param_name="res",
                param_value="0.8",
                outcome_metric="score",
                outcome_value=0.95,
                project_id="p1",
                context="",
                created_at="2024-06-01T00:00:00+00:00",
            )
        )
        insights = curator.distill_new_bundles()
        assert any(i.insight_type == "parameter_combo" for i in insights)

    def test_project_similarity_insight(self, curator, cbkb):
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b1",
                project_id="p1",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["a", "b"],
                phases=["p1"],
                summary="",
            )
        )
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b2",
                project_id="p2",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["a", "b"],
                phases=["p1"],
                summary="",
            )
        )
        insights = curator.distill_new_bundles()
        assert any(i.insight_type == "project_similarity" for i in insights)

    def test_since_filter(self, curator, cbkb):
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="old",
                project_id="p1",
                created_at="2023-01-01T00:00:00+00:00",
                skills_used=["a"],
                phases=["p1"],
                summary="",
            )
        )
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="new",
                project_id="p1",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["a"],
                phases=["p1"],
                summary="",
            )
        )
        insights = curator.distill_new_bundles(since="2024-01-01T00:00:00+00:00")
        source_ids = [sid for i in insights for sid in i.source_ids]
        assert "old" not in source_ids


class TestClusterTopics:
    def test_empty_no_clusters(self, curator):
        assert curator.cluster_topics() == []

    def test_clustering_groups_similar_nodes(self, curator, cbkb):
        for i in range(4):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id=f"p{i}",
                    created_at="2024-06-01T00:00:00+00:00",
                    skills_used=["scanpy_qc", "scanpy_pca"],
                    phases=["qc", "pca"],
                    summary="",
                )
            )
        clusters = curator.cluster_topics()
        assert len(clusters) >= 1
        assert all(isinstance(c, TopicCluster) for c in clusters)

    def test_common_skills_extracted(self, curator, cbkb):
        for i in range(3):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id=f"p{i}",
                    created_at="2024-06-01T00:00:00+00:00",
                    skills_used=["skill_a", "skill_b"],
                    phases=["p"],
                    summary="",
                )
            )
        clusters = curator.cluster_topics()
        assert len(clusters) >= 1
        assert "skill_a" in clusters[0].common_skills or "skill_b" in clusters[0].common_skills


class TestGenerateNarrative:
    def test_basic_narrative(self, curator, cbkb):
        now = datetime.now(timezone.utc).isoformat()
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b1",
                project_id="p1",
                created_at=now,
                skills_used=["scanpy_qc"],
                phases=["qc"],
                summary="",
            )
        )
        narrative = curator.generate_narrative()
        assert isinstance(narrative, NarrativeReport)
        assert narrative.total_experiments >= 1

    def test_top_anomalies_surface(self, curator, cbkb):
        now = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            cbkb.archive_anomaly(
                AnomalyRecord(
                    id=f"a{i}",
                    project_id="p1",
                    phase_type="qc",
                    summary="High dropout",
                    flags=["flag"],
                    recommendations=["rec"],
                    severity="warning",
                    created_at=now,
                )
            )
        narrative = curator.generate_narrative()
        assert narrative.total_anomalies == 3
        assert any(phase == "qc" for phase, _ in narrative.top_anomalies)

    def test_insights_from_parameter_lore(self, curator, cbkb):
        now = datetime.now(timezone.utc).isoformat()
        cbkb.add_parameter_lore(
            ParameterLoreEntry(
                id="pl1",
                skill_id="s1",
                param_name="m",
                param_value="0.8",
                outcome_metric="score",
                outcome_value=0.99,
                project_id="p1",
                context="",
                created_at=now,
            )
        )
        narrative = curator.generate_narrative()
        assert any(i.insight_type == "parameter_lore" for i in narrative.insights)


class TestProposeSOPUpdates:
    def test_no_proposals_when_no_clusters(self, curator):
        assert curator.propose_sop_updates() == []

    def test_propose_new_sop_from_large_cluster(self, curator, cbkb):
        for i in range(5):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id=f"p{i}",
                    created_at="2024-06-01T00:00:00+00:00",
                    skills_used=["scanpy_qc", "scanpy_pca"],
                    phases=["qc", "pca"],
                    summary="",
                )
            )
        proposals = curator.propose_sop_updates()
        assert any(p.sop_id.startswith("sop_proposal_") for p in proposals)

    def test_detect_divergence(self, curator, cbkb):
        # Create SOP derived from bundles
        cbkb.create_sop(
            LabSOP(
                id="sop1",
                name="Old SOP",
                category="test",
                template={},
                derived_from_bundle_ids=["b1", "b2"],
            )
        )
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b1",
                project_id="p1",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["a", "b"],
                phases=["p"],
                summary="",
            )
        )
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b2",
                project_id="p2",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["c", "d"],
                phases=["p"],
                summary="",
            )
        )
        proposals = curator.propose_sop_updates()
        assert any(p.sop_id.startswith("sop_divergence_") for p in proposals)


class TestAutoLinkExperiments:
    def test_no_nodes_no_edges(self, curator):
        assert curator.auto_link_experiments() == 0

    def test_links_similar_experiments(self, curator, cbkb):
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b1",
                project_id="p1",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["scanpy_qc", "scanpy_pca"],
                phases=["qc"],
                summary="",
            )
        )
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b2",
                project_id="p2",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["scanpy_qc", "scanpy_pca"],
                phases=["qc"],
                summary="",
            )
        )
        created = curator.auto_link_experiments()
        assert created == 1
        related = cbkb.find_related_experiments("b1")
        assert len(related) == 1
        assert related[0][1] == "shares_skill"

    def test_no_duplicate_edges(self, curator, cbkb):
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b1",
                project_id="p1",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["scanpy_qc"],
                phases=["qc"],
                summary="",
            )
        )
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b2",
                project_id="p2",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["scanpy_qc"],
                phases=["qc"],
                summary="",
            )
        )
        first = curator.auto_link_experiments()
        second = curator.auto_link_experiments()
        assert first == 1
        assert second == 0


class TestRunFullCuration:
    def test_returns_summary_dict(self, curator, cbkb):
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b1",
                project_id="p1",
                created_at="2024-06-01T00:00:00+00:00",
                skills_used=["a"],
                phases=["p"],
                summary="",
            )
        )
        summary = curator.run_full_curation()
        assert isinstance(summary, dict)
        assert "distilled_insights" in summary
        assert "topic_clusters" in summary
        assert "narrative_generated" in summary
        assert "sop_proposals" in summary
        assert "auto_linked_edges" in summary
        assert "timestamp" in summary
