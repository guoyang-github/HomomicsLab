"""Tests for NextflowInputBuilder."""

from pathlib import Path

import pytest

from homomics_lab.agent.plan.models import DataState as PlanDataState, Phase, PlanResult
from homomics_lab.workflow.nextflow_inputs import NextflowInputBuilder


@pytest.fixture
def builder(tmp_path):
    # Simulate a project workspace.
    ws_dir = tmp_path / "workspaces" / "proj_1"
    (ws_dir / "data").mkdir(parents=True)
    (ws_dir / "data" / "sample1.h5ad").write_text("dummy")
    (ws_dir / "data" / "sample2.h5ad").write_text("dummy")
    return NextflowInputBuilder(tmp_path, "proj_1")


def test_build_includes_outdir_and_flattened_params(builder):
    plan_result = PlanResult(
        phases=[
            Phase(phase_type="qc", required=True, parameters={"min_genes": 200}),
            Phase(phase_type="normalize", required=True, parameters={"target_sum": 10000}),
        ],
        strategy_name="test",
        data_state=PlanDataState(),
    )
    inputs = builder.build(plan_result, template_name=None)

    assert "outdir" in inputs
    assert inputs["min_genes"] == 200
    assert inputs["target_sum"] == 10000


def test_single_cell_template_generates_samplesheet(builder):
    plan_result = PlanResult(
        phases=[Phase(phase_type="qc", required=True)],
        strategy_name="single_cell_standard",
        data_state=PlanDataState(),
    )
    inputs = builder.build(plan_result, template_name="single_cell")

    assert "samplesheet" in inputs
    samplesheet = Path(inputs["samplesheet"])
    assert samplesheet.exists()
    text = samplesheet.read_text(encoding="utf-8")
    assert "sample,input_path" in text
    assert "sample1" in text
    assert "sample2" in text


def test_rnaseq_template_generates_samplesheet(builder):
    plan_result = PlanResult(
        phases=[Phase(phase_type="qc", required=True)],
        strategy_name="rnaseq",
        data_state=PlanDataState(),
    )
    inputs = builder.build(plan_result, template_name="rnaseq")

    assert "samplesheet" in inputs
    samplesheet = Path(inputs["samplesheet"])
    assert samplesheet.exists()
    text = samplesheet.read_text(encoding="utf-8")
    assert "sample,fastq_1,fastq_2,strandedness" in text


def test_auto_mode_uses_first_data_file(builder):
    plan_result = PlanResult(
        phases=[Phase(phase_type="qc", required=True)],
        strategy_name="generic",
        data_state=PlanDataState(),
    )
    inputs = builder.build(plan_result, template_name=None)

    assert "input_path" in inputs
    assert Path(inputs["input_path"]).exists()
