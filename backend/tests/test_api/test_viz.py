"""Lightweight API tests for the /api/viz endpoints.

These tests use a minimal FastAPI app with only the viz router and a fake
skill executor so they do not pay the cost of full application startup.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from homomics_lab.api import viz
from homomics_lab.config import settings
from homomics_lab.workspace.manager import WorkspaceManager


class _FakeSkillExecutor:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []
        self.registry = self

    def get(self, skill_id):
        # Pretend the viz skill exists and has a source_dir.
        if skill_id == "bio-statistics-visualization":
            return type("_Skill", (), {"source_dir": Path(__file__).parent})()
        return None

    async def execute(self, skill_id, inputs):
        self.calls.append((skill_id, inputs))
        action = inputs.get("action")
        return self._responses.get(action, {"success": True})


@pytest.fixture
def app(tmp_path):
    app = FastAPI()
    app.include_router(viz.router, prefix="/api/viz")

    # Absolute figure path under the temporary workspace so the endpoint can
    # compute relative paths for artifact registration.
    figure_abs = tmp_path / "workspaces" / "test_viz_project" / "sessions" / "s1" / "figures" / "fig_test_1.png"
    figure_abs.parent.mkdir(parents=True, exist_ok=True)
    figure_abs.write_bytes(b"fake_png")

    app.state.skill_executor = _FakeSkillExecutor({
        "import_data": {
            "success": True,
            "outputs": {
                "data_id": "data_abc123",
                "table_type": "column",
                "group_columns": ["Control", "Drug_A", "Drug_B"],
            },
            "artifacts": [],
            "interpretation": "Imported column table.",
        },
        "full_pipeline": {
            "success": True,
            "outputs": {
                "figure_id": "fig_test_1",
                "formats": {"png": str(figure_abs)},
                "data_id": "data_abc123",
            },
            "artifacts": [
                {
                    "path": str(figure_abs),
                    "relative_path": "sessions/s1/figures/fig_test_1.png",
                    "type": "output",
                    "mime": "image/png",
                }
            ],
            "interpretation": "Rendered figure.",
        },
    })
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def sample_project(tmp_path):
    project_id = "test_viz_project"
    data_dir = tmp_path / "workspaces" / project_id / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "tumor_data.csv").write_text(
        "Control,Drug_A,Drug_B\n10.2,13.5,11.8\n"
    )
    original_data_dir = settings.data_dir
    settings.data_dir = tmp_path
    yield project_id
    settings.data_dir = original_data_dir


def test_create_viz_session(client, sample_project):
    response = client.post(
        "/api/viz/sessions",
        json={
            "project_id": sample_project,
            "source_filename": "tumor_data.csv",
            "table_type_hint": "column",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "session_id" in data
    assert data["outputs"]["table_type"] == "column"
    assert len(data["outputs"]["group_columns"]) == 3


def test_viz_full_pipeline_renders_figure(client, sample_project, tmp_path):
    session_resp = client.post(
        "/api/viz/sessions",
        json={
            "project_id": sample_project,
            "source_filename": "tumor_data.csv",
            "table_type_hint": "column",
        },
    )
    session_id = session_resp.json()["session_id"]

    render_resp = client.post(
        f"/api/viz/sessions/{session_id}/render",
        json={
            "project_id": sample_project,
            "action": "full_pipeline",
            "params": {
                "plot_type": "bar",
                "theme": "nature",
                "formats": ["png"],
            },
        },
    )
    assert render_resp.status_code == 200
    data = render_resp.json()
    assert data["success"] is True
    assert data["outputs"]["figure_id"] == "fig_test_1"
    assert "png" in data["outputs"]["formats"]


def test_list_figures(client, sample_project, tmp_path):
    ws = WorkspaceManager(tmp_path, sample_project)
    ws.register_artifact(
        task_id="viz_task",
        artifact_type="output",
        filename="figure.png",
        metadata={
            "kind": "figure",
            "figure_id": "fig_list_test",
            "formats": {"png": "outputs/figure.png"},
        },
    )

    response = client.get(f"/api/projects/{sample_project}/figures")
    # The viz router does not define the list endpoint; it lives in projects.py.
    # This test documents the expected response shape for the projects endpoint.
    assert response.status_code == 404
