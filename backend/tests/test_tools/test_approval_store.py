"""Tests for persistent tool approval store."""


import pytest

from homomics_lab.tools.approval_store import PersistentApprovalStore


@pytest.fixture
def store(tmp_path):
    return PersistentApprovalStore(db_path=tmp_path / "approvals.db")


def test_create_and_get_request(store):
    req = store.create_request(tool_name="shell_exec", arguments={"cmd": "ls"}, risk_level="high")
    assert req.call_id
    loaded = store.get(req.call_id)
    assert loaded is not None
    assert loaded.tool_name == "shell_exec"
    assert not loaded.approved


def test_approve_and_list_pending(store):
    req1 = store.create_request(tool_name="shell_exec", arguments={}, risk_level="high")
    req2 = store.create_request(tool_name="file_delete", arguments={}, risk_level="high")
    store.approve(req1.call_id, resolver="user", reason="trusted")
    assert store.is_approved(req1.call_id)
    assert not store.is_approved(req2.call_id)
    pending = store.list_pending()
    assert len(pending) == 1
    assert pending[0].call_id == req2.call_id


def test_persistence_across_instances(tmp_path):
    store1 = PersistentApprovalStore(db_path=tmp_path / "approvals.db")
    req = store1.create_request(tool_name="x", arguments={}, risk_level="high")

    store2 = PersistentApprovalStore(db_path=tmp_path / "approvals.db")
    loaded = store2.get(req.call_id)
    assert loaded is not None
    assert loaded.tool_name == "x"
