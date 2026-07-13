"""Tests for append-only JSONL provenance and content-addressed env snapshots."""

import json
import threading

from homomics_lab.provenance.env_snapshot import (
    collect_distributions,
    env_hash,
    env_snapshot,
    store_env_snapshot,
)
from homomics_lab.provenance.jsonl import (
    append_jsonl,
    record_provenance,
    record_run,
)
from homomics_lab.provenance.models import FileRecord


def _read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_append_jsonl_writes_one_record_per_line(tmp_path):
    path = tmp_path / "trail.jsonl"
    append_jsonl(path, {"a": 1})
    append_jsonl(path, {"b": 2})
    lines = _read_lines(path)
    assert lines == [{"a": 1}, {"b": 2}]


def test_append_jsonl_is_thread_safe(tmp_path):
    path = tmp_path / "concurrent.jsonl"
    n = 25

    def worker(i):
        append_jsonl(path, {"i": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = _read_lines(path)
    assert len(lines) == n
    assert sorted(entry["i"] for entry in lines) == list(range(n))


def test_store_env_snapshot_is_content_addressed(tmp_path):
    metadata = tmp_path / ".metadata"
    first = store_env_snapshot(metadata)
    second = store_env_snapshot(metadata)

    assert first
    assert first == second
    env_files = list((metadata / "env").glob("*.json"))
    assert len(env_files) == 1
    assert env_files[0].stem == first

    snapshot = json.loads(env_files[0].read_text(encoding="utf-8"))
    assert "python" in snapshot
    assert "packages" in snapshot
    assert isinstance(snapshot["packages"], list)


def test_env_hash_is_stable_for_identical_input():
    snap = env_snapshot()
    assert env_hash(snap) == env_hash(snap)
    assert collect_distributions() == sorted(
        set(collect_distributions()), key=str.lower
    )


def test_record_provenance_one_line_per_output(tmp_path):
    outputs = [
        FileRecord(path="out/a.h5ad", checksum="aaa", size_bytes=10),
        FileRecord(path="out/b.csv", checksum="bbb", size_bytes=20),
    ]
    record_provenance(
        tmp_path,
        job_id="job-1",
        skill_id="bio-x",
        skill_version="1.0.0",
        code_hash="code123",
        env_hash="env456",
        output_files=outputs,
        status="COMPLETED",
        started_at="2026-01-01T00:00:00",
        ended_at="2026-01-01T00:01:00",
    )

    lines = _read_lines(tmp_path / ".metadata" / "provenance.jsonl")
    assert len(lines) == 2
    paths = {line["output"]["path"] for line in lines}
    assert paths == {"out/a.h5ad", "out/b.csv"}
    for line in lines:
        assert line["job_id"] == "job-1"
        assert line["skill_id"] == "bio-x"
        assert line["code_hash"] == "code123"
        assert line["env_hash"] == "env456"


def test_record_provenance_without_outputs_still_links_run(tmp_path):
    record_provenance(
        tmp_path,
        job_id="job-2",
        skill_id="bio-y",
        skill_version="1.0.0",
        code_hash="c",
        env_hash="e",
        output_files=[],
        status="COMPLETED",
        started_at=None,
        ended_at=None,
    )
    lines = _read_lines(tmp_path / ".metadata" / "provenance.jsonl")
    assert len(lines) == 1
    assert lines[0]["output"] is None
    assert lines[0]["job_id"] == "job-2"


def test_record_run_appends_summary(tmp_path):
    record_run(tmp_path, {"job_id": "job-3", "status": "COMPLETED"})
    record_run(tmp_path, {"job_id": "job-4", "status": "FAILED"})
    lines = _read_lines(tmp_path / ".metadata" / "runs.jsonl")
    assert [line["job_id"] for line in lines] == ["job-3", "job-4"]
