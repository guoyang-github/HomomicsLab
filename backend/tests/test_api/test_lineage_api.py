"""Tests for the lineage/provenance API endpoint."""

from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.workspace.manager import WorkspaceManager


def test_get_project_lineage_returns_nodes_and_edges(client: TestClient, tmp_path, monkeypatch):
    """The lineage endpoint should return a graph built from workspace artifacts."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    # Create a project through the API so the database record exists.
    create_resp = client.post("/api/projects", json={
        "name": "Lineage Test Project",
        "description": "Testing provenance graph API",
    })
    assert create_resp.status_code == 200
    project_id = create_resp.json()["id"]

    # Register a simple lineage chain directly in the workspace.
    ws = WorkspaceManager(settings.data_dir, project_id)
    raw_path = ws.register_artifact(
        task_id="load_data",
        artifact_type="data",
        filename="raw.csv",
    )
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("sample_id,value\n1,10\n")
    ws.update_artifact_checksum("data/raw.csv")

    intermediate_path = ws.register_artifact(
        task_id="normalize",
        artifact_type="intermediate",
        filename="normalized.csv",
        source_task="load_data",
    )
    intermediate_path.parent.mkdir(parents=True, exist_ok=True)
    intermediate_path.write_text("sample_id,norm_value\n1,0.5\n")
    ws.update_artifact_checksum("intermediate/normalized.csv")

    output_path = ws.register_artifact(
        task_id="report",
        artifact_type="output",
        filename="report.csv",
        source_task="normalize",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("sample_id,result\n1,pass\n")
    ws.update_artifact_checksum("output/report.csv")

    response = client.get(f"/api/lineage/projects/{project_id}")
    assert response.status_code == 200, response.text
    data = response.json()

    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2

    node_types = {n["type"] for n in data["nodes"]}
    assert node_types == {"data", "intermediate", "output"}

    edge_pairs = {(e["from_node"], e["to_node"]) for e in data["edges"]}
    # The exact node IDs are UUIDs; verify topology by task chain instead.
    nodes_by_task = {n["created_by_task"]: n["node_id"] for n in data["nodes"]}
    assert (
        nodes_by_task["load_data"],
        nodes_by_task["normalize"],
    ) in edge_pairs
    assert (
        nodes_by_task["normalize"],
        nodes_by_task["report"],
    ) in edge_pairs
