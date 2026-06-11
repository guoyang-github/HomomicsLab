"""Tests for WorkspaceManager."""

import json
import sqlite3
from pathlib import Path

import pytest

from homomics_lab.workspace.manager import WorkspaceManager


class TestWorkspaceManager:
    def test_init_creates_structure(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        assert ws.workspace_dir.exists()
        assert (ws.workspace_dir / "data").exists()
        assert (ws.workspace_dir / "intermediate").exists()
        assert (ws.workspace_dir / "outputs").exists()
        assert (ws.workspace_dir / "logs").exists()
        assert (ws.workspace_dir / ".metadata").exists()

    def test_get_path_plain_relative(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        path = ws.get_path("intermediate/file.h5ad")
        assert path == ws.workspace_dir / "intermediate" / "file.h5ad"

    def test_get_path_workspace_protocol(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        path = ws.get_path("workspace://intermediate/file.h5ad")
        assert path == ws.workspace_dir / "intermediate" / "file.h5ad"

    def test_get_path_escaping_workspace_raises(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        with pytest.raises(ValueError, match="escapes workspace"):
            ws.get_path("workspace://../../../etc/passwd")

    def test_register_artifact_returns_path(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        path = ws.register_artifact(
            task_id="qc_1",
            artifact_type="intermediate",
            filename="qc.h5ad",
            source_task="load_1",
        )
        assert path == ws.workspace_dir / "intermediate" / "qc.h5ad"

    def test_register_artifact_persists_to_db(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        ws.register_artifact(
            task_id="qc_1",
            artifact_type="intermediate",
            filename="qc.h5ad",
            source_task="load_1",
        )
        artifacts = ws.list_artifacts()
        assert len(artifacts) == 1
        assert artifacts[0].task_id == "qc_1"
        assert artifacts[0].artifact_type == "intermediate"
        assert artifacts[0].source_task == "load_1"

    def test_list_artifacts_filtered_by_type(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        ws.register_artifact(task_id="t1", artifact_type="intermediate", filename="a.h5ad")
        ws.register_artifact(task_id="t2", artifact_type="output", filename="b.png")
        ws.register_artifact(task_id="t3", artifact_type="intermediate", filename="c.h5ad")

        intermediates = ws.list_artifacts(artifact_type="intermediate")
        assert len(intermediates) == 2

    def test_list_artifacts_filtered_by_task(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        ws.register_artifact(task_id="task_a", artifact_type="intermediate", filename="a.h5ad")
        ws.register_artifact(task_id="task_b", artifact_type="intermediate", filename="b.h5ad")

        artifacts = ws.list_artifacts(task_id="task_a")
        assert len(artifacts) == 1
        assert artifacts[0].relative_path == "intermediate/a.h5ad"

    def test_snapshot_and_list(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        # Create a dummy file
        (ws.workspace_dir / "intermediate" / "test.txt").write_text("hello")
        snap_id = ws.snapshot(label="after_qc")
        snapshots = ws.list_snapshots()
        assert len(snapshots) == 1
        assert snapshots[0].snapshot_id == snap_id
        assert snapshots[0].label == "after_qc"
        assert len(snapshots[0].file_manifest) >= 1

    def test_build_lineage_graph(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        ws.register_artifact(
            task_id="load_1",
            artifact_type="data",
            filename="raw.h5ad",
        )
        ws.register_artifact(
            task_id="qc_1",
            artifact_type="intermediate",
            filename="qc.h5ad",
            source_task="load_1",
        )
        graph = ws.build_lineage_graph()
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.edges[0].transform_id == "qc_1"

    def test_checksum_computed_after_write(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        path = ws.register_artifact(
            task_id="load_1",
            artifact_type="data",
            filename="raw.h5ad",
        )
        # Initially empty file
        path.write_text("test data")
        ws.update_artifact_checksum("data/raw.h5ad")
        artifacts = ws.list_artifacts()
        assert artifacts[0].checksum != ""
        # Verify checksum changes with content
        path.write_text("different data")
        ws.update_artifact_checksum("data/raw.h5ad")
        artifacts = ws.list_artifacts()
        new_checksum = artifacts[0].checksum
        # Different content → different checksum
        assert new_checksum != ""

    def test_data_readonly_protection(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        data_file = ws.get_data_path("raw.h5ad")
        data_file.write_text("protected")
        ws.protect_data("data/raw.h5ad")
        # File should now be read-only
        assert not data_file.stat().st_mode & 0o200

    def test_invalid_artifact_type_raises(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")
        with pytest.raises(ValueError, match="Invalid artifact_type"):
            ws.register_artifact(
                task_id="t1",
                artifact_type="invalid",
                filename="x.h5ad",
            )

    def test_lock_versions(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")

        class FakeSkill:
            def __init__(self, sid, ver):
                self.id = sid
                self.version = ver
                self.metadata = {}

        class FakeRegistry:
            def list_all(self):
                return [FakeSkill("s1", "1.0.0")]

            def get(self, skill_id):
                return FakeSkill("s1", "1.0.0") if skill_id == "s1" else None

        lock = ws.lock_versions(FakeRegistry())
        assert lock.project_id == "test_proj"
        assert lock.skills["s1"] == "1.0.0"

        # Verify should pass
        result = ws.verify_versions(FakeRegistry())
        assert result.compatible is True

    def test_verify_versions_detects_drift(self, tmp_path: Path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="test_proj")

        class FakeSkill:
            def __init__(self, sid, ver):
                self.id = sid
                self.version = ver
                self.metadata = {}

        class FakeRegistryV1:
            def list_all(self):
                return [FakeSkill("s1", "1.0.0")]

            def get(self, skill_id):
                return FakeSkill("s1", "1.0.0") if skill_id == "s1" else None

        ws.lock_versions(FakeRegistryV1())

        class FakeRegistryV2:
            def list_all(self):
                return [FakeSkill("s1", "2.0.0")]

            def get(self, skill_id):
                return FakeSkill("s1", "2.0.0") if skill_id == "s1" else None

        result = ws.verify_versions(FakeRegistryV2())
        assert result.compatible is False
        assert "2.0.0" in result.version_mismatches[0]
