"""Tests for the files upload/list/read API endpoints."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.storage import get_storage_backend, reset_storage_backend


@pytest.fixture(autouse=True)
def _reset_storage_backend():
    """Ensure each test starts with a fresh storage backend singleton."""
    reset_storage_backend()
    yield
    reset_storage_backend()


def test_upload_file_streams_to_storage_and_workspace(client: TestClient, tmp_path, monkeypatch):
    """Uploading a file should stream it to object storage, raw/, and workspace data/."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "storage_backend", "local")

    project_id = "proj_upload_1"
    filename = "hello.txt"
    content = b"streamed upload content"

    response = client.post(
        "/api/files/upload",
        params={"project_id": project_id},
        files={"file": (filename, BytesIO(content), "text/plain")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["filename"] == filename
    assert data["project_id"] == project_id
    assert data["size"] == len(content)
    assert data["storage_uri"].startswith("file://")

    # Raw project copy.
    raw_path = tmp_path / "raw" / project_id / filename
    assert raw_path.read_bytes() == content

    # Workspace data mirror.
    ws_path = tmp_path / "workspaces" / project_id / "data" / filename
    assert ws_path.read_bytes() == content

    # Object store copy.
    backend = get_storage_backend()
    assert backend.exists(f"{project_id}/uploads/{filename}")


def test_upload_file_rejects_oversized_stream(client: TestClient, tmp_path, monkeypatch):
    """A file larger than max_upload_file_bytes should be rejected with 413."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr("homomics_lab.api.files.MAX_UPLOAD_FILE_BYTES", 10)

    response = client.post(
        "/api/files/upload",
        params={"project_id": "proj_upload_2"},
        files={"file": ("big.txt", BytesIO(b"x" * 100), "text/plain")},
    )

    assert response.status_code == 413
    assert "maximum upload size" in response.json()["detail"]
