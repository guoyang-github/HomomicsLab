"""Tests for the streaming file preview endpoint with Range support."""

from fastapi.testclient import TestClient

from homomics_lab.config import settings


def _write_project_file(tmp_path, project_id: str, rel_path: str, content: bytes) -> None:
    """Create a file under the project's raw directory."""
    target = tmp_path / "raw" / project_id / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def test_preview_full_file_stream(client: TestClient, tmp_path, monkeypatch):
    """A request without Range should stream the full file with Accept-Ranges."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "proj_preview_full"
    content = b"Hello, streaming preview world!"
    _write_project_file(tmp_path, project_id, "notes.txt", content)

    response = client.get(
        "/api/files/preview",
        params={"project_id": project_id, "path": "notes.txt"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Type"] == "text/plain"
    assert int(response.headers["Content-Length"]) == len(content)
    assert response.content == content


def test_preview_range_request_returns_206(client: TestClient, tmp_path, monkeypatch):
    """A valid Range request should return 206 with correct Content-Range."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "proj_preview_range"
    content = b"abcdefghijklmnopqrstuvwxyz"
    _write_project_file(tmp_path, project_id, "letters.bin", content)

    response = client.get(
        "/api/files/preview",
        params={"project_id": project_id, "path": "letters.bin"},
        headers={"Range": "bytes=5-14"},
    )

    assert response.status_code == 206, response.text
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Range"] == f"bytes 5-14/{len(content)}"
    assert int(response.headers["Content-Length"]) == 10
    assert response.content == content[5:15]


def test_preview_suffix_range_returns_last_bytes(client: TestClient, tmp_path, monkeypatch):
    """A suffix Range request (bytes=-N) returns the last N bytes."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "proj_preview_suffix"
    content = b"0123456789"
    _write_project_file(tmp_path, project_id, "numbers.bin", content)

    response = client.get(
        "/api/files/preview",
        params={"project_id": project_id, "path": "numbers.bin"},
        headers={"Range": "bytes=-4"},
    )

    assert response.status_code == 206, response.text
    assert response.headers["Content-Range"] == f"bytes 6-9/{len(content)}"
    assert response.content == b"6789"


def test_preview_range_open_ended(client: TestClient, tmp_path, monkeypatch):
    """An open-ended Range (bytes=N-) returns from offset to end of file."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "proj_preview_open"
    content = b"0123456789"
    _write_project_file(tmp_path, project_id, "numbers.bin", content)

    response = client.get(
        "/api/files/preview",
        params={"project_id": project_id, "path": "numbers.bin"},
        headers={"Range": "bytes=7-"},
    )

    assert response.status_code == 206, response.text
    assert response.headers["Content-Range"] == f"bytes 7-9/{len(content)}"
    assert response.content == b"789"


def test_preview_unsatisfiable_range_returns_416(client: TestClient, tmp_path, monkeypatch):
    """A Range beyond the file size should return 416 with Content-Range */size."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "proj_preview_416"
    content = b"short"
    _write_project_file(tmp_path, project_id, "short.bin", content)

    response = client.get(
        "/api/files/preview",
        params={"project_id": project_id, "path": "short.bin"},
        headers={"Range": "bytes=100-200"},
    )

    assert response.status_code == 416
    assert response.headers["Content-Range"] == f"bytes */{len(content)}"


def test_preview_exceeds_full_preview_limit(client: TestClient, tmp_path, monkeypatch):
    """A non-ranged request for a file above the preview limit should return 413."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(
        "homomics_lab.api.files._MAX_PREVIEW_BYTES",
        10,
    )
    project_id = "proj_preview_big"
    content = b"x" * 100
    _write_project_file(tmp_path, project_id, "big.bin", content)

    response = client.get(
        "/api/files/preview",
        params={"project_id": project_id, "path": "big.bin"},
    )

    assert response.status_code == 413
    assert "preview size limit" in response.json()["detail"]
