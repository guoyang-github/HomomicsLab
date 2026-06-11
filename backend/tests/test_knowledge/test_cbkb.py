"""Tests for Computational Biology Knowledge Base (CBKB)."""

import json
import pytest

from homomics_lab.knowledge.cbkb import (
    AnomalyRecord,
    CBKB,
    ExperimentEdge,
    ExperimentNode,
    LabSOP,
    ParameterLoreEntry,
    SkillEvolutionRecord,
)


@pytest.fixture
def cbkb(tmp_path):
    return CBKB(base_dir=tmp_path)


class TestExperimentGraph:

    def test_add_and_get_node(self, cbkb):
        node = ExperimentNode(
            bundle_id="b1",
            project_id="proj_1",
            created_at="2024-01-01T00:00:00+00:00",
            skills_used=["scanpy_qc", "scanpy_cluster"],
            phases=["qc", "cluster"],
            summary="Test analysis",
        )
        cbkb.add_experiment_node(node)
        loaded = cbkb.get_experiment_node("b1")
        assert loaded is not None
        assert loaded.skills_used == ["scanpy_qc", "scanpy_cluster"]

    def test_add_and_find_edges(self, cbkb):
        n1 = ExperimentNode(bundle_id="b1", project_id="p1", created_at="2024-01-01T00:00:00+00:00", skills_used=[], phases=[])
        n2 = ExperimentNode(bundle_id="b2", project_id="p1", created_at="2024-01-02T00:00:00+00:00", skills_used=[], phases=[])
        cbkb.add_experiment_node(n1)
        cbkb.add_experiment_node(n2)

        edge = ExperimentEdge(from_bundle="b1", to_bundle="b2", edge_type="shares_skill", strength=0.9)
        cbkb.add_experiment_edge(edge)

        related = cbkb.find_related_experiments("b1")
        assert len(related) == 1
        assert related[0][0] == "b2"
        assert related[0][1] == "shares_skill"

    def test_find_related_filtered_by_type(self, cbkb):
        n1 = ExperimentNode(bundle_id="b1", project_id="p1", created_at="2024-01-01T00:00:00+00:00", skills_used=[], phases=[])
        n2 = ExperimentNode(bundle_id="b2", project_id="p1", created_at="2024-01-02T00:00:00+00:00", skills_used=[], phases=[])
        n3 = ExperimentNode(bundle_id="b3", project_id="p1", created_at="2024-01-03T00:00:00+00:00", skills_used=[], phases=[])
        for n in [n1, n2, n3]:
            cbkb.add_experiment_node(n)

        cbkb.add_experiment_edge(ExperimentEdge("b1", "b2", "shares_skill", 0.9))
        cbkb.add_experiment_edge(ExperimentEdge("b1", "b3", "derived_from", 0.5))

        related = cbkb.find_related_experiments("b1", edge_type="shares_skill")
        assert len(related) == 1
        assert related[0][0] == "b2"


class TestParameterLore:

    def test_add_and_query(self, cbkb):
        entry = ParameterLoreEntry(
            id="pl1",
            skill_id="scanpy_cluster",
            param_name="resolution",
            param_value="0.8",
            outcome_metric="n_clusters",
            outcome_value=8.0,
            project_id="p1",
            context="PBMC dataset",
            created_at="2024-01-01T00:00:00+00:00",
        )
        cbkb.add_parameter_lore(entry)

        results = cbkb.query_parameter_lore(skill_id="scanpy_cluster")
        assert len(results) == 1
        assert results[0].param_value == "0.8"

    def test_query_filtered(self, cbkb):
        for val, out in [("0.6", 6.0), ("0.8", 8.0), ("0.8", 9.0)]:
            cbkb.add_parameter_lore(ParameterLoreEntry(
                id=f"pl_{val}_{out}",
                skill_id="scanpy_cluster",
                param_name="resolution",
                param_value=val,
                outcome_metric="n_clusters",
                outcome_value=out,
                project_id="p1",
                context="",
                created_at="2024-01-01T00:00:00+00:00",
            ))

        results = cbkb.query_parameter_lore(param_name="resolution", min_outcome=7.0)
        assert len(results) == 2

    def test_suggest_parameters(self, cbkb):
        cbkb.add_parameter_lore(ParameterLoreEntry(
            id="pl1", skill_id="s", param_name="m", param_value="0.6",
            outcome_metric="score", outcome_value=0.9, project_id="p1",
            context="", created_at="2024-01-01T00:00:00+00:00",
        ))
        cbkb.add_parameter_lore(ParameterLoreEntry(
            id="pl2", skill_id="s", param_name="m", param_value="0.8",
            outcome_metric="score", outcome_value=0.7, project_id="p1",
            context="", created_at="2024-01-01T00:00:00+00:00",
        ))
        suggestions = cbkb.suggest_parameters("s")
        assert len(suggestions) == 2
        # 0.6 has higher mean score
        assert suggestions[0]["param_value"] == "0.6"


class TestAnomalyArchive:

    def test_archive_and_query(self, cbkb):
        rec = AnomalyRecord(
            id="a1",
            project_id="p1",
            phase_type="qc",
            summary="High filter rate",
            flags=["High cell filtering rate: 80%"],
            recommendations=["Check data quality"],
            severity="critical",
            created_at="2024-01-01T00:00:00+00:00",
        )
        cbkb.archive_anomaly(rec)

        results = cbkb.query_anomalies(phase_type="qc")
        assert len(results) == 1
        assert results[0].severity == "critical"

    def test_query_by_severity(self, cbkb):
        for i, sev in enumerate(["warning", "critical", "warning"]):
            cbkb.archive_anomaly(AnomalyRecord(
                id=f"a_{sev}_{i}", project_id="p1", phase_type="qc",
                summary="x", flags=[], recommendations=[], severity=sev,
                created_at="2024-01-01T00:00:00+00:00",
            ))
        assert len(cbkb.query_anomalies(severity="critical")) == 1
        assert len(cbkb.query_anomalies(severity="warning")) == 2

    def test_anomaly_stats(self, cbkb):
        cbkb.archive_anomaly(AnomalyRecord(
            id="a1", project_id="p1", phase_type="qc", summary="x",
            flags=[], recommendations=[], severity="warning", created_at="2024-01-01T00:00:00+00:00",
        ))
        stats = cbkb.get_anomaly_stats()
        assert stats["total"] == 1
        assert stats["by_phase"]["qc"] == 1
        assert stats["by_severity"]["warning"] == 1


class TestLabSOP:

    def test_create_and_get(self, cbkb):
        sop = LabSOP(
            id="sop1",
            name="Standard PBMC QC",
            category="single_cell",
            template={"min_genes": 200, "min_cells": 3},
            derived_from_bundle_ids=["b1", "b2"],
            version="1.0",
            locked=False,
        )
        cbkb.create_sop(sop)
        loaded = cbkb.get_sop("sop1")
        assert loaded is not None
        assert loaded.name == "Standard PBMC QC"
        assert loaded.template["min_genes"] == 200

    def test_list_by_category(self, cbkb):
        cbkb.create_sop(LabSOP(id="s1", name="A", category="sc", template={}, derived_from_bundle_ids=[]))
        cbkb.create_sop(LabSOP(id="s2", name="B", category="sc", template={}, derived_from_bundle_ids=[]))
        cbkb.create_sop(LabSOP(id="s3", name="C", category="spatial", template={}, derived_from_bundle_ids=[]))
        assert len(cbkb.list_sops(category="sc")) == 2
        assert len(cbkb.list_sops()) == 3


class TestSkillEvolutionLog:

    def test_log_and_query(self, cbkb):
        rec = SkillEvolutionRecord(
            id="se1",
            from_skill="scanpy_qc",
            to_skill="scanpy_pca",
            edge_type="followed_by",
            old_state="CANDIDATE",
            new_state="CONFIRMED",
            trigger="5_successful_executions",
            confidence=0.95,
            timestamp="2024-01-01T00:00:00+00:00",
        )
        cbkb.log_skill_evolution(rec)

        results = cbkb.get_skill_evolution("scanpy_qc")
        assert len(results) == 1
        assert results[0].new_state == "CONFIRMED"

    def test_get_all(self, cbkb):
        cbkb.log_skill_evolution(SkillEvolutionRecord(
            id="se1", from_skill="a", to_skill="b", edge_type="f",
            old_state="C", new_state="C", trigger="t", confidence=0.5,
            timestamp="2024-01-01T00:00:00+00:00",
        ))
        assert len(cbkb.get_skill_evolution()) == 1


class TestCrossLayerInsights:

    def test_project_summary(self, cbkb):
        cbkb.add_experiment_node(ExperimentNode(
            bundle_id="b1", project_id="p1", created_at="2024-01-01T00:00:00+00:00",
            skills_used=[], phases=[], summary="",
        ))
        cbkb.archive_anomaly(AnomalyRecord(
            id="a1", project_id="p1", phase_type="qc", summary="x",
            flags=[], recommendations=[], severity="warning", created_at="2024-01-01T00:00:00+00:00",
        ))
        cbkb.add_parameter_lore(ParameterLoreEntry(
            id="pl1", skill_id="s", param_name="m", param_value="v",
            outcome_metric="o", outcome_value=1.0, project_id="p1",
            context="", created_at="2024-01-01T00:00:00+00:00",
        ))

        summary = cbkb.get_project_summary("p1")
        assert summary["experiments_recorded"] == 1
        assert summary["anomalies_recorded"] == 1
        assert summary["parameter_lore_entries"] == 1
