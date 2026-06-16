"""Tests for nf-core result ingestion into workspaces."""


import pytest

from homomics_lab.config import settings
from homomics_lab.nfcore_results import (
    DEFAULT_PATTERNS,
    NFCoreResultIngester,
    ResultPattern,
    WORKSPACE_TYPE_MAP,
)
from homomics_lab.workspace.manager import WorkspaceManager


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return WorkspaceManager(base_dir=tmp_path, project_id="proj_test")


def test_ingest_maps_artifact_types(workspace):
    """Semantic nf-core artifact labels must map to WorkspaceManager types."""
    for pattern in DEFAULT_PATTERNS:
        assert pattern.artifact_type in WORKSPACE_TYPE_MAP, (
            f"{pattern.artifact_type} is not mapped to a workspace type"
        )


def test_ingest_copies_files_to_workspace(workspace, tmp_path):
    output_dir = tmp_path / "nfcore_out"
    output_dir.mkdir()
    report = output_dir / "multiqc_report.html"
    report.write_text("<html>multiqc</html>")
    plot = output_dir / "figures" / "heatmap.png"
    plot.parent.mkdir()
    plot.write_bytes(b"\x89PNG\r\n\x1a\n")

    ingester = NFCoreResultIngester(workspace)
    artifacts = ingester.ingest(output_dir, task_id="task_1")

    assert len(artifacts) == 2
    types = {a["artifact_type"] for a in artifacts}
    assert types == {"report", "plot"}

    # Files must exist inside the workspace.
    assert (workspace.workspace_dir / "output" / "multiqc_report.html").exists()
    assert (workspace.workspace_dir / "output" / "figures" / "heatmap.png").exists()


def test_ingest_records_metadata(workspace, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "quant.sf").write_text("quant data")

    ingester = NFCoreResultIngester(workspace)
    ingester.ingest(output_dir, task_id="task_meta", source_task="nf-core-rnaseq")

    records = workspace.list_artifacts(task_id="task_meta")
    assert len(records) == 1
    record = records[0]
    assert record.artifact_type == "data"
    assert record.source_task == "nf-core-rnaseq"
    assert record.metadata.get("nfcore_artifact_type") == "data"
    assert record.relative_path == "data/quant.sf"


def test_ingest_multiqc_summary(workspace, tmp_path):
    output_dir = tmp_path / "out" / "multiqc_data"
    output_dir.mkdir(parents=True)
    summary = {
        "report_general_stats_data": {
            "sample_1": {"pct_dup": 5.0},
            "sample_2": {"pct_dup": 3.0},
        }
    }
    import json

    (output_dir / "multiqc_data.json").write_text(json.dumps(summary))

    ingester = NFCoreResultIngester(workspace)
    result = ingester.ingest_multiqc_summary(output_dir.parent)

    assert result is not None
    assert result["sample_count"] == 2


def test_ingest_skips_missing_directory(workspace, tmp_path):
    ingester = NFCoreResultIngester(workspace)
    artifacts = ingester.ingest(tmp_path / "does_not_exist", task_id="task_x")
    assert artifacts == []


def test_ingest_deduplicates_files(workspace, tmp_path):
    """Overlapping globs should not register the same file twice."""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "table.csv").write_text("a,b\n1,2")

    patterns = [
        ResultPattern(artifact_type="table", globs=["**/*.csv"], description="csv"),
        ResultPattern(artifact_type="table", globs=["**/*.csv"], description="csv again"),
    ]
    ingester = NFCoreResultIngester(workspace, patterns=patterns)
    artifacts = ingester.ingest(output_dir, task_id="task_dedup")

    assert len(artifacts) == 1
