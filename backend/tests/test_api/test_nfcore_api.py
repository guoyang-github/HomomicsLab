"""Smoke tests for the nf-core API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def enable_nfcore(monkeypatch):
    monkeypatch.setattr(settings, "nfcore_enabled", True)


@pytest.fixture
def disable_nfcore(monkeypatch):
    monkeypatch.setattr(settings, "nfcore_enabled", False)


class FakePipeline:
    name = "nf-core-rnaseq"
    description = "RNA-Seq"
    topics = ["rna-seq"]
    stars = 100
    default_branch = "master"
    github_url = "https://github.com/nf-core/rnaseq"
    latest_release = "3.14.0"


def test_nfcore_disabled_returns_404(client, disable_nfcore):
    response = client.get("/api/nfcore/pipelines")
    assert response.status_code == 404


def test_list_pipelines(client, enable_nfcore):
    manager = MagicMock()
    manager.list_pipelines.return_value = [FakePipeline()]
    with patch("homomics_lab.api.nfcore.get_nfcore_manager", return_value=manager):
        response = client.get("/api/nfcore/pipelines")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "nf-core-rnaseq"


def test_get_schema(client, enable_nfcore):
    manager = MagicMock()
    manager.load_schema.return_value = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "nf-core-rnaseq",
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "samplesheet",
                "format": "file-path",
            },
            "outdir": {"type": "string", "default": "./results"},
        },
        "required": ["input"],
    }
    with patch("homomics_lab.api.nfcore.get_nfcore_manager", return_value=manager):
        response = client.get("/api/nfcore/schema/rnaseq")
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline"] == "rnaseq"
    assert any(field["name"] == "input" for field in data["fields"])


def test_validate_params(client, enable_nfcore):
    manager = MagicMock()
    manager.load_schema.return_value = {
        "type": "object",
        "properties": {"input": {"type": "string"}},
        "required": ["input"],
    }
    with patch("homomics_lab.api.nfcore.get_nfcore_manager", return_value=manager):
        response = client.post("/api/nfcore/validate", json={"pipeline": "rnaseq", "params": {}})
    assert response.status_code == 400

    with patch("homomics_lab.api.nfcore.get_nfcore_manager", return_value=manager):
        response = client.post(
            "/api/nfcore/validate", json={"pipeline": "rnaseq", "params": {"input": "samplesheet.csv"}}
        )
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_ingest_endpoint(client, enable_nfcore, tmp_path):
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    (output_dir / "multiqc_report.html").write_text("<html>report</html>")

    response = client.post(
        "/api/nfcore/ingest",
        json={
            "project_id": "proj_api",
            "output_dir": str(output_dir),
            "task_id": "task_api",
            "source_task": "nf-core-rnaseq",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == "proj_api"
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["artifact_type"] == "report"
