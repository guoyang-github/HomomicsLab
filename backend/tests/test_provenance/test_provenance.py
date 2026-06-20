"""Tests for provenance recording and RO-Crate export."""


import pytest

from homomics_lab.provenance.models import ExecutionProvenance, FileRecord
from homomics_lab.provenance.recorder import ProvenanceRecorder, sha256_file
from homomics_lab.provenance.rocrate import ROCrateExporter


@pytest.fixture
def recorder(tmp_path):
    return ProvenanceRecorder(db_path=tmp_path / "provenance.db")


def test_sha256_file(tmp_path):
    p = tmp_path / "hello.txt"
    p.write_text("hello")
    digest = sha256_file(p)
    assert len(digest) == 64


def test_record_and_load_provenance(recorder, tmp_path):
    p = tmp_path / "input.txt"
    p.write_text("input data")
    prov = ExecutionProvenance(
        execution_id="exec-1",
        skill_id="test-skill",
        skill_version="1.0.0",
        input_files=[FileRecord(path=str(p), checksum=sha256_file(p), size_bytes=p.stat().st_size)],
        sandbox_backend="local",
    )
    recorder.record(prov)
    loaded = recorder.list_by_project("nonexistent")
    assert loaded == []


def test_rocrate_export(tmp_path):
    crate_dir = tmp_path / "crate"
    exporter = ROCrateExporter(crate_dir)
    prov = ExecutionProvenance(
        execution_id="exec-2",
        skill_id="test-skill",
        skill_version="1.0.0",
        sandbox_backend="container",
        container_image="python:3.10-slim",
        container_digest="sha256:abc",
    )
    path = exporter.export("proj-1", [prov])
    assert path.exists()
    assert (path / "ro-crate-metadata.json").exists()
