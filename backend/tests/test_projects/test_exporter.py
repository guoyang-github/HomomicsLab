"""Tests for project export/import."""

import zipfile
from pathlib import Path

import pytest

from homomics_lab.projects import ProjectExporter, ProjectImporter
from homomics_lab.context.experiment_logger import ExperimentLogger


@pytest.fixture
def exporter(tmp_path, monkeypatch):
    from homomics_lab.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return ProjectExporter("test_proj")


@pytest.fixture
def importer(tmp_path, monkeypatch):
    from homomics_lab.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return ProjectImporter()


class TestProjectExporter:
    def test_export_creates_archive(self, exporter, tmp_path):
        archive = exporter.export_to(tmp_path / "out.homomics")
        assert archive.exists()
        assert zipfile.is_zipfile(archive)

    def test_archive_contains_metadata(self, exporter, tmp_path):
        archive = exporter.export_to(tmp_path / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            assert "project.json" in zf.namelist()
            meta = __import__("json").loads(zf.read("project.json"))
            assert meta["project_id"] == "test_proj"

    def test_archive_contains_memory_md(self, exporter, tmp_path):
        # Create MEMORY.md
        project_dir = tmp_path / "projects" / "test_proj"
        project_dir.mkdir(parents=True)
        (project_dir / "MEMORY.md").write_text("# Test Log")

        archive = exporter.export_to(tmp_path / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            assert "MEMORY.md" in zf.namelist()
            assert b"# Test Log" in zf.read("MEMORY.md")

    def test_archive_contains_notes(self, exporter, tmp_path):
        logger = ExperimentLogger("test_proj")
        import asyncio
        asyncio.run(logger.record(text="Note 1", step="QC"))

        archive = exporter.export_to(tmp_path / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            assert "notes.json" in zf.namelist()
            notes = __import__("json").loads(zf.read("notes.json"))
            assert len(notes) == 1
            assert notes[0]["text"] == "Note 1"


class TestProjectImporter:
    def test_import_from_archive(self, exporter, importer, tmp_path):
        archive = exporter.export_to(tmp_path / "test.homomics")
        imported_id = importer.import_from(archive)

        assert imported_id is not None
        assert "test_proj" in imported_id

    def test_import_restores_memory_md(self, exporter, importer, tmp_path):
        project_dir = tmp_path / "projects" / "test_proj"
        project_dir.mkdir(parents=True)
        (project_dir / "MEMORY.md").write_text("# Imported Log")

        archive = exporter.export_to(tmp_path / "test.homomics")
        imported_id = importer.import_from(archive)

        restored = tmp_path / "projects" / imported_id / "MEMORY.md"
        assert restored.exists()
        assert "# Imported Log" in restored.read_text()

    def test_import_restores_notes(self, exporter, importer, tmp_path):
        logger = ExperimentLogger("test_proj")
        import asyncio
        asyncio.run(logger.record(text="Test note", tags=["test"]))

        archive = exporter.export_to(tmp_path / "test.homomics")
        imported_id = importer.import_from(archive)

        # Verify notes in SQLite
        import sqlite3
        db_path = tmp_path / "projects" / imported_id / "experiment.db"
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT text FROM experiment_notes").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "Test note"

    def test_import_invalid_archive(self, importer, tmp_path):
        bad_file = tmp_path / "not_a_zip.homomics"
        bad_file.write_text("not a zip")
        with pytest.raises(ValueError, match="Not a valid archive"):
            importer.import_from(bad_file)
