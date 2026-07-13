"""Tests for GitWorkspaceSnapshot and WorkspaceManager git integration."""

import shutil
from unittest.mock import patch

import pytest

from homomics_lab.workspace.git_snapshot import GitWorkspaceSnapshot
from homomics_lab.workspace.manager import WorkspaceManager


@pytest.fixture
def git_ws(tmp_path):
    """WorkspaceManager with a temporary base directory."""
    return WorkspaceManager(base_dir=tmp_path, project_id="proj_git")


@pytest.fixture
def snapshot(git_ws):
    """GitWorkspaceSnapshot bound to the temporary workspace."""
    return GitWorkspaceSnapshot(git_ws.workspace_dir)


@pytest.mark.skipif(not shutil.which("git"), reason="git not available")
class TestGitWorkspaceSnapshot:
    def test_init_creates_hidden_repo(self, snapshot):
        assert snapshot.init() is True
        assert snapshot.git_dir.exists()
        assert (snapshot.git_dir / "HEAD").exists()

    def test_commit_returns_hash(self, snapshot):
        snapshot.init()
        file_path = snapshot.workspace_dir / "data" / "raw.txt"
        file_path.write_text("hello")

        commit_hash = snapshot.commit("test-label", "task_1")

        assert commit_hash is not None
        assert len(commit_hash) == 40

    def test_commit_message_includes_task_id_and_label(self, snapshot):
        snapshot.init()
        (snapshot.workspace_dir / "data" / "raw.txt").write_text("hello")

        snapshot.commit("pre-run", "job_1")
        commits = snapshot.list_commits()

        assert len(commits) == 1
        assert commits[0]["message"] == "job_1: pre-run"

    def test_list_commits_empty_before_any_commit(self, snapshot):
        snapshot.init()
        assert snapshot.list_commits() == []

    def test_list_commits_returns_multiple_commits(self, snapshot):
        snapshot.init()
        (snapshot.workspace_dir / "data" / "a.txt").write_text("a")
        snapshot.commit("first", "task_1")
        (snapshot.workspace_dir / "data" / "b.txt").write_text("b")
        snapshot.commit("second", "task_2")

        commits = snapshot.list_commits()

        assert len(commits) == 2
        assert commits[0]["message"] == "task_2: second"
        assert commits[1]["message"] == "task_1: first"

    def test_diff_between_commits(self, snapshot):
        snapshot.init()
        data_file = snapshot.workspace_dir / "data" / "raw.txt"
        data_file.write_text("v1")
        hash_a = snapshot.commit("first", "task_1")

        data_file.write_text("v2")
        hash_b = snapshot.commit("second", "task_1")

        diff = snapshot.diff(hash_a, hash_b)

        assert "raw.txt" in diff

    def test_diff_returns_empty_for_unknown_commits(self, snapshot):
        snapshot.init()
        assert snapshot.diff("deadbeef", "cafebabe") == ""

    def test_restore_reverts_files(self, snapshot):
        snapshot.init()
        data_file = snapshot.workspace_dir / "data" / "raw.txt"
        data_file.write_text("v1")
        hash_a = snapshot.commit("first", "task_1")

        data_file.write_text("v2")
        snapshot.commit("second", "task_1")

        restored = snapshot.restore(hash_a)

        assert restored is True
        assert data_file.read_text() == "v1"

    def test_restore_returns_false_for_unknown_commit(self, snapshot):
        snapshot.init()
        assert snapshot.restore("deadbeef") is False

    def test_gitignore_excludes_metadata_git_dir(self, snapshot):
        snapshot.init()
        (snapshot.workspace_dir / "data" / "raw.txt").write_text("hello")
        snapshot.commit("first", "task_1")

        gitignore = snapshot.workspace_dir / ".gitignore"
        assert gitignore.exists()
        assert ".metadata/git" in gitignore.read_text()


class TestGitWorkspaceSnapshotMissingGit:
    def test_init_returns_false_when_git_missing(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_no_git")
        snapshot = GitWorkspaceSnapshot(ws.workspace_dir)
        with patch("shutil.which", return_value=None):
            assert snapshot.init() is False

    def test_commit_returns_none_when_git_missing(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_no_git")
        snapshot = GitWorkspaceSnapshot(ws.workspace_dir)
        with patch("shutil.which", return_value=None):
            assert snapshot.commit("label", "task") is None

    def test_list_commits_returns_empty_when_git_missing(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_no_git")
        snapshot = GitWorkspaceSnapshot(ws.workspace_dir)
        with patch("shutil.which", return_value=None):
            assert snapshot.list_commits() == []

    def test_diff_returns_empty_when_git_missing(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_no_git")
        snapshot = GitWorkspaceSnapshot(ws.workspace_dir)
        with patch("shutil.which", return_value=None):
            assert snapshot.diff("a", "b") == ""

    def test_restore_returns_false_when_git_missing(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_no_git")
        snapshot = GitWorkspaceSnapshot(ws.workspace_dir)
        with patch("shutil.which", return_value=None):
            assert snapshot.restore("a") is False


class TestWorkspaceManagerGitIntegration:
    @pytest.mark.skipif(not shutil.which("git"), reason="git not available")
    def test_create_git_snapshot(self, git_ws):
        (git_ws.workspace_dir / "outputs" / "result.txt").write_text("result")
        commit_hash = git_ws.create_git_snapshot("post-run", "job_1")

        assert commit_hash is not None
        snapshots = git_ws.list_git_snapshots()
        assert any(s["hash"] == commit_hash for s in snapshots)

    @pytest.mark.skipif(not shutil.which("git"), reason="git not available")
    def test_list_git_snapshots_empty_initially(self, git_ws):
        assert git_ws.list_git_snapshots() == []

    @pytest.mark.skipif(not shutil.which("git"), reason="git not available")
    def test_restore_git_snapshot(self, git_ws):
        data_file = git_ws.workspace_dir / "data" / "raw.txt"
        data_file.write_text("v1")
        commit_hash = git_ws.create_git_snapshot("first", "job_1")

        data_file.write_text("v2")
        restored = git_ws.restore_git_snapshot(commit_hash)

        assert restored is True
        assert data_file.read_text() == "v1"

    def test_git_snapshot_lazy_property(self, git_ws):
        assert isinstance(git_ws.git_snapshot, GitWorkspaceSnapshot)
        assert git_ws.git_snapshot.workspace_dir == git_ws.workspace_dir
