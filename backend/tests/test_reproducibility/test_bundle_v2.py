"""Tests for ReproducibilityBundle v2 additions: env hash, git snapshot, provenance files, and zip export."""

import json
import shutil
import zipfile
from unittest.mock import patch

import pytest

from homomics_lab.reproducibility.bundle import (
    EnvironmentLock,
    ReproducibilityBundle,
)
from homomics_lab.reproducibility.engine import ReproducibilityEngine
from homomics_lab.workspace.manager import WorkspaceManager


def _fast_capture() -> EnvironmentLock:
    return EnvironmentLock(
        python_version="3.12.0",
        pip_freeze="mock-pkg==1.0\n",
        conda_env_export="",
        system_info={"platform": "linux", "machine": "x86_64"},
    )


@pytest.fixture
def engine(tmp_path):
    ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_v2")
    engine = ReproducibilityEngine(ws)
    with patch.object(engine, "_capture_environment", _fast_capture):
        engine.start_analysis(project_id="proj_v2", random_seed=42)
    return engine


def _make_git_commits(workspace, count: int = 2):
    if not shutil.which("git"):
        return []
    for i in range(count):
        file_path = workspace.workspace_dir / "data" / f"file_{i}.txt"
        file_path.write_text(f"content {i}")
        workspace.create_git_snapshot(f"step_{i}", f"task_{i}")
    return workspace.list_git_snapshots()


class TestReproducibilityBundleV2:
    def test_finalize_includes_env_snapshot_hash(self, engine):
        bundle = engine.finalize()

        assert bundle.env_snapshot_hash is not None
        assert len(bundle.env_snapshot_hash) == 64

    @pytest.mark.skipif(not shutil.which("git"), reason="git not available")
    def test_finalize_includes_latest_git_snapshot(self, engine):
        commits = _make_git_commits(engine.workspace, count=2)

        bundle = engine.finalize()

        assert bundle.git_snapshot is not None
        assert bundle.git_snapshot["hash"] == commits[0]["hash"]

    def test_finalize_includes_provenance_files(self, engine):
        metadata_dir = engine.workspace.get_path(".metadata")
        (metadata_dir / "provenance.jsonl").write_text("{}")
        (metadata_dir / "runs.jsonl").write_text("{}")

        bundle = engine.finalize()

        assert "provenance.jsonl" in bundle.provenance_files
        assert "runs.jsonl" in bundle.provenance_files

    def test_finalize_includes_version_lock(self, engine):
        metadata_dir = engine.workspace.get_path(".metadata")
        version_lock = {"project_id": "proj_v2", "skills": {}}
        (metadata_dir / "version.lock").write_text(json.dumps(version_lock))

        bundle = engine.finalize()

        assert bundle.version_lock == version_lock

    def test_bundle_roundtrip_includes_v2_fields(self, engine):
        bundle = engine.finalize()
        bundle.env_snapshot_hash = "abc123"
        bundle.git_snapshot = {"hash": "deadbeef", "message": "test"}
        bundle.provenance_files = {"provenance.jsonl": "{}"}
        bundle.version_lock = {"skills": {}}

        restored = ReproducibilityBundle.from_json(bundle.to_json())

        assert restored.env_snapshot_hash == "abc123"
        assert restored.git_snapshot == {"hash": "deadbeef", "message": "test"}
        assert restored.provenance_files == {"provenance.jsonl": "{}"}
        assert restored.version_lock == {"skills": {}}


class TestReproducibilityExportZip:
    def test_export_zip_creates_zip(self, engine, tmp_path):
        output_path = tmp_path / "bundle.zip"

        result_path = engine.export_zip(output_path)

        assert result_path.exists()
        assert zipfile.is_zipfile(result_path)

    def test_export_zip_contains_bundle_json(self, engine, tmp_path):
        output_path = tmp_path / "bundle.zip"
        engine.export_zip(output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert "reproducibility_bundle.json" in names
            bundle_json = zf.read("reproducibility_bundle.json").decode("utf-8")
            bundle = ReproducibilityBundle.from_json(bundle_json)
            assert bundle.project_id == "proj_v2"

    def test_export_zip_contains_provenance_files(self, engine, tmp_path):
        metadata_dir = engine.workspace.get_path(".metadata")
        (metadata_dir / "provenance.jsonl").write_text('{"line": 1}\n')
        (metadata_dir / "runs.jsonl").write_text('{"run": 1}\n')

        output_path = tmp_path / "bundle.zip"
        engine.export_zip(output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert "provenance.jsonl" in names
            assert "runs.jsonl" in names
            assert zf.read("provenance.jsonl").decode("utf-8") == '{"line": 1}\n'

    def test_export_zip_contains_env_snapshot(self, engine, tmp_path):
        output_path = tmp_path / "bundle.zip"
        engine.export_zip(output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert any(name.startswith("env/") and name.endswith(".json") for name in names)

    @pytest.mark.skipif(not shutil.which("git"), reason="git not available")
    def test_export_zip_contains_git_snapshot(self, engine, tmp_path):
        _make_git_commits(engine.workspace, count=1)

        output_path = tmp_path / "bundle.zip"
        engine.export_zip(output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert "git_snapshot.json" in names
            git_snapshot = json.loads(zf.read("git_snapshot.json").decode("utf-8"))
            assert "hash" in git_snapshot

    def test_export_zip_contains_version_lock(self, engine, tmp_path):
        metadata_dir = engine.workspace.get_path(".metadata")
        version_lock = {"project_id": "proj_v2", "skills": {"qc": "1.0"}}
        (metadata_dir / "version.lock").write_text(json.dumps(version_lock))

        output_path = tmp_path / "bundle.zip"
        engine.export_zip(output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert "version.lock" in names
            stored = json.loads(zf.read("version.lock").decode("utf-8"))
            assert stored["skills"]["qc"] == "1.0"
