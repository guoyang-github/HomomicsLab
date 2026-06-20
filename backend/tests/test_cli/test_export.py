"""Tests for the `homomics export` CLI command."""

from pathlib import Path

from homomics_lab.cli.commands.export import register_export_parser, run_export
from homomics_lab.provenance.models import ExecutionProvenance


def test_register_export_parser():
    import argparse
    subparsers = argparse.ArgumentParser().add_subparsers()
    register_export_parser(subparsers)
    parser = subparsers.choices["export"]
    assert parser is not None


def test_run_export_rocrate(monkeypatch, tmp_path):
    record = ExecutionProvenance(
        execution_id="exec-1",
        skill_id="test_skill",
        skill_version="1.0",
        project_id="proj-1",
    )

    class FakeRecorder:
        def list_by_project(self, project_id):
            assert project_id == "proj-1"
            return [record]

    export_calls = []

    class FakeExporter:
        def __init__(self, output_dir):
            self.output_dir = Path(output_dir)

        def export(self, project_id, provenance_records, project_files=None):
            export_calls.append((project_id, provenance_records))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "ro-crate-metadata.json").write_text("{}")

    monkeypatch.setattr("homomics_lab.cli.commands.export.ProvenanceRecorder", FakeRecorder)
    monkeypatch.setattr("homomics_lab.cli.commands.export.ROCrateExporter", FakeExporter)

    class Args:
        project_id = "proj-1"
        format = "rocrate"
        output = str(tmp_path / "out")

    code = run_export(Args())
    assert code == 0
    assert len(export_calls) == 1
    assert export_calls[0][0] == "proj-1"
    assert Path(Args.output + ".zip").exists()
