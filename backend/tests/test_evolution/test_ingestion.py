"""Tests for CBKB ingestion after workflow execution."""

import pytest

from homomics_lab.evolution.ingestion import CBKBIngestionService
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.models.common import TaskStatus
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@pytest.fixture
def cbkb(tmp_path):
    return CBKB(base_dir=tmp_path)


@pytest.fixture
def ingestion(cbkb):
    return CBKBIngestionService(cbkb)


@pytest.fixture
def simple_tree():
    return TaskTree([
        TaskNode(
            id="t1",
            name="qc",
            description="Quality control",
            skills_required=["scanpy_qc"],
            parameters={"min_genes": 200},
            status=TaskStatus.COMPLETED,
        ),
        TaskNode(
            id="t2",
            name="normalization",
            description="Normalize counts",
            skills_required=["scanpy_normalize"],
            parameters={"target_sum": 10000},
            status=TaskStatus.COMPLETED,
        ),
    ])


class TestCBKBIngestion:
    def test_ingest_creates_experiment_node(self, ingestion, cbkb, simple_tree):
        bundle_id = ingestion.ingest_workflow(
            project_id="proj_1",
            task_tree=simple_tree,
            success=True,
            duration_seconds=120.0,
        )

        node = cbkb.get_experiment_node(bundle_id)
        assert node is not None
        assert node.project_id == "proj_1"
        assert "scanpy_qc" in node.skills_used
        assert "scanpy_normalize" in node.skills_used
        assert node.metadata["success"] is True
        assert node.metadata["duration_seconds"] == 120.0

    def test_ingest_creates_parameter_lore(self, ingestion, cbkb, simple_tree):
        ingestion.ingest_workflow(
            project_id="proj_1",
            task_tree=simple_tree,
            success=True,
        )

        lore = cbkb.query_parameter_lore(skill_id="scanpy_qc")
        assert any(e.param_name == "min_genes" for e in lore)

        norm_lore = cbkb.query_parameter_lore(skill_id="scanpy_normalize")
        assert any(e.param_name == "target_sum" for e in norm_lore)

    def test_failed_task_low_outcome(self, ingestion, cbkb, simple_tree):
        simple_tree.tasks[0].status = TaskStatus.FAILED
        ingestion.ingest_workflow(
            project_id="proj_1",
            task_tree=simple_tree,
            success=False,
        )

        lore = cbkb.query_parameter_lore(skill_id="scanpy_qc")
        assert all(e.outcome_value == 0.0 for e in lore)

    def test_ingest_skips_internal_params(self, ingestion, cbkb, simple_tree):
        simple_tree.tasks[0].parameters["_internal"] = "secret"
        ingestion.ingest_workflow(
            project_id="proj_1",
            task_tree=simple_tree,
            success=True,
        )

        lore = cbkb.query_parameter_lore(skill_id="scanpy_qc")
        assert not any(e.param_name == "_internal" for e in lore)
