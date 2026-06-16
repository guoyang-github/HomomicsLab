import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from homomics_lab.config import settings
from homomics_lab.nfcore_integration import NFCoreManager, NFCorePipeline


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return NFCoreManager(cache_dir=tmp_path / "nfcore")


def test_normalize_name(manager):
    assert manager._normalize_name("rnaseq") == "nf-core-rnaseq"
    assert manager._normalize_name("nf-core-rnaseq") == "nf-core-rnaseq"
    assert manager._normalize_name("nfcore-rnaseq") == "nf-core-rnaseq"


def test_suggest_pipeline(manager):
    assert manager.suggest_pipeline("rnaseq_analysis") == "nf-core-rnaseq"
    assert manager.suggest_pipeline("single_cell_analysis") == "nf-core-scrnaseq"
    assert manager.suggest_pipeline("unknown") is None


def test_list_from_github(manager):
    mock_repos = [
        {
            "name": "nf-core-rnaseq",
            "description": "RNA-Seq pipeline",
            "topics": ["rna-seq"],
            "stargazers_count": 500,
            "default_branch": "master",
            "html_url": "https://github.com/nf-core/rnaseq",
            "archived": False,
            "disabled": False,
        },
        {
            "name": "tools",
            "description": "nf-core tools",
            "topics": [],
            "stargazers_count": 200,
            "default_branch": "master",
            "html_url": "https://github.com/nf-core/tools",
            "archived": False,
            "disabled": False,
        },
    ]

    def mock_urlopen(url, timeout=None):
        response = MagicMock()
        response.read.return_value = json.dumps(mock_repos).encode("utf-8")
        response.__enter__ = lambda self: self
        response.__exit__ = lambda *args: None
        return response

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        pipelines = manager._list_from_github()

    assert len(pipelines) == 1
    assert pipelines[0].name == "nf-core-rnaseq"


def test_run_pipeline_builds_cmd(manager, tmp_path):
    # Create a fake cached pipeline directory.
    pipeline_dir = manager.cache_dir / "nf-core-rnaseq"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "main.nf").write_text("workflow {}")

    result = manager.run_pipeline(
        "rnaseq",
        params={"input": "samplesheet.csv", "outdir": "results"},
        version="3.14.0",
        profiles=["docker"],
    )

    assert result["pipeline"] == "rnaseq"
    assert result["version"] == "3.14.0"
    assert Path(result["pipeline_dir"]).exists()
    assert "nextflow run" in result["nextflow_cmd"]
    assert "-profile docker" in result["nextflow_cmd"]
    assert "--input samplesheet.csv" in result["nextflow_cmd"]


def test_list_cached_pipelines(manager):
    pipeline_dir = manager.cache_dir / "nf-core-rnaseq"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "main.nf").write_text("workflow {}")

    cached = manager._list_cached_pipelines()
    assert len(cached) == 1
    assert cached[0].name == "nf-core-rnaseq"
