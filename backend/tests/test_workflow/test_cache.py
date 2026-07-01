"""Tests for WorkflowCache content-addressable storage."""

import pytest

from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.tasks.models import TaskNode
from homomics_lab.workflow.cache import WorkflowCache


@pytest.fixture
def cache(tmp_path) -> WorkflowCache:
    return WorkflowCache(cache_dir=tmp_path / "workflow_cache")


def test_compute_hash_is_stable(cache):
    assert cache.compute_hash({"a": 1, "b": [2, 3]}) == cache.compute_hash({"b": [2, 3], "a": 1})


def test_put_and_get_roundtrip(cache):
    cache.put("key1", {"status": "completed", "value": 42}, metadata={"task": "demo"})
    entry = cache.get("key1")
    assert entry is not None
    assert entry.success is True
    assert entry.result["value"] == 42
    assert entry.metadata["task"] == "demo"


def test_get_missing_returns_none(cache):
    assert cache.get("nonexistent") is None


def test_invalid_entry_returns_none(cache):
    entry_dir = cache._entry_dir("bad")
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / "metadata.json").write_text("not json")
    (entry_dir / "result.json").write_text("{}")
    assert cache.get("bad") is None


def test_artifacts_are_copied(cache, tmp_path):
    out_file = tmp_path / "output.txt"
    out_file.write_text("hello")
    cache.put("key2", {"status": "completed"}, artifacts=[out_file])
    entry = cache.get("key2")
    assert len(entry.artifacts) == 1
    assert entry.artifacts[0].read_text() == "hello"


def test_clear_removes_all_entries(cache):
    cache.put("a", {"status": "completed"})
    cache.put("b", {"status": "completed"})
    assert cache.clear() == 2
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_compute_task_key_changes_with_parameter(cache):
    task = TaskNode(id="t1", name="qc", description="QC", skills_required=["scanpy_qc"], parameters={"x": 1})
    key1 = cache.compute_task_key(task)
    task.parameters["x"] = 2
    key2 = cache.compute_task_key(task)
    assert key1 != key2


def test_compute_task_key_changes_with_upstream_result(cache):
    task = TaskNode(id="t2", name="norm", description="Normalize", skills_required=["scanpy_norm"], dependencies=["t1"])
    key1 = cache.compute_task_key(task, upstream_results={"t1": {"cells": 100}})
    key2 = cache.compute_task_key(task, upstream_results={"t1": {"cells": 200}})
    assert key1 != key2


def test_compute_task_key_includes_skill_version(cache):
    task = TaskNode(id="t1", name="qc", description="QC", skills_required=["scanpy_qc"], parameters={"x": 1})
    skill_v1 = SkillDefinition(
        id="scanpy_qc",
        name="scanpy_qc",
        version="1.0.0",
        category="test",
        input_schema=SkillInputSchema(),
    )
    skill_v2 = SkillDefinition(
        id="scanpy_qc",
        name="scanpy_qc",
        version="2.0.0",
        category="test",
        input_schema=SkillInputSchema(),
    )
    key1 = cache.compute_task_key(task, skill=skill_v1)
    key2 = cache.compute_task_key(task, skill=skill_v2)
    assert key1 != key2


def test_compute_task_key_hashes_file_contents(cache, tmp_path):
    input_file = tmp_path / "counts.csv"
    input_file.write_text("gene,cell\nA,1")
    task = TaskNode(
        id="t1",
        name="qc",
        description="QC",
        skills_required=["scanpy_qc"],
        parameters={"input": str(input_file)},
    )
    key1 = cache.compute_task_key(task)
    input_file.write_text("gene,cell\nA,2")
    key2 = cache.compute_task_key(task)
    assert key1 != key2


def test_large_file_hash_uses_size_mtime(cache, tmp_path, monkeypatch):
    input_file = tmp_path / "big.csv"
    input_file.write_text("x")
    monkeypatch.setattr(cache, "_content_hash_limit", 1)
    key1 = cache._hash_file(input_file)
    input_file.write_text("yy")
    # Size changed -> hash should change.
    key2 = cache._hash_file(input_file)
    assert key1 != key2
