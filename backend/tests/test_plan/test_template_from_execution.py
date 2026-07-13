"""Tests for saving execution plans and open-agent runs as templates."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
from homomics_lab.api.templates import router


@pytest.fixture
def client(tmp_path):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api/templates")

    # Inject a file-backed store into app state for isolation.
    store = AnalysisTemplateStore(data_dir=tmp_path)
    app.state.analysis_template_store = store

    yield TestClient(app)


class TestTemplateFromExecution:
    def test_requires_plan_id_or_task_tree(self, client):
        response = client.post(
            "/api/templates/from-execution",
            json={"name": "My template"},
        )
        assert response.status_code == 400
        assert "plan_id" in response.json()["detail"]

    def test_creates_template_from_task_tree(self, client, tmp_path):
        task_tree = {
            "tasks": [
                {"name": "qc", "description": "QC step"},
                {"name": "clustering", "description": "Cluster step"},
            ],
            "intent_analysis_type": "single_cell_analysis",
        }
        response = client.post(
            "/api/templates/from-execution",
            json={
                "name": "Saved scRNA-seq",
                "description": "Saved from a previous run",
                "task_tree": task_tree,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["template_id"]

        store = AnalysisTemplateStore(data_dir=tmp_path)
        template = store.get_template(data["template_id"])
        assert template is not None
        assert template.name == "Saved scRNA-seq"
        assert "qc" in template.phase_defaults
        assert "clustering" in template.phase_defaults
        assert "single_cell_analysis" in template.applicable_intents


class TestTemplateFromOpenAgent:
    def test_creates_template_from_open_agent(self, client, tmp_path):
        response = client.post(
            "/api/templates/from-open-agent",
            json={
                "name": "Open Agent Run",
                "user_message": "Compare scRNA-seq and spatial transcriptomics",
                "phase_outputs": [
                    {"phase": "explore"},
                    {"phase": "summarize"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["template_id"]

        store = AnalysisTemplateStore(data_dir=tmp_path)
        template = store.get_template(data["template_id"])
        assert template is not None
        assert template.name == "Open Agent Run"
        assert "explore" in template.phase_defaults
        assert "summarize" in template.phase_defaults
        assert "Compare scRNA-seq and spatial transcriptomics" in template.applicable_intents
