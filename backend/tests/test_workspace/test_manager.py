"""Tests for WorkspaceManager snapshot and restore."""

import pytest

from homomics_lab.workspace.manager import WorkspaceManager


@pytest.fixture
def workspace(tmp_path):
    return WorkspaceManager(base_dir=tmp_path, project_id="proj_1")


def test_snapshot_copies_files(workspace):
    data_file = workspace.get_data_path("raw.txt")
    data_file.write_text("hello")

    snapshot_id = workspace.snapshot("pre_qc")

    snapshot_files_dir = (
        workspace.workspace_dir
        / workspace.METADATA_SUBDIR
        / "snapshots"
        / snapshot_id
        / "files"
    )
    copied = snapshot_files_dir / "data" / "raw.txt"
    assert copied.exists()
    assert copied.read_text() == "hello"


def test_restore_rolls_back_files(workspace):
    data_file = workspace.get_data_path("raw.txt")
    data_file.write_text("hello")

    snapshot_id = workspace.snapshot("pre_qc")

    data_file.write_text("modified")
    new_file = workspace.get_intermediate_path("new.txt")
    new_file.write_text("i am new")

    workspace.restore(snapshot_id)

    assert data_file.read_text() == "hello"
    assert not new_file.exists()


def test_restore_raises_for_missing_snapshot(workspace):
    with pytest.raises(ValueError):
        workspace.restore("missing_snapshot_id")
