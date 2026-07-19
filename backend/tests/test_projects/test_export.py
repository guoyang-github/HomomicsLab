"""Tests for rich project configuration export (Phase 4.6)."""

import json
import zipfile

import pytest

from homomics_lab.config import settings
from homomics_lab.context.project_state import ProjectState, ProjectStateManager
from homomics_lab.knowledge.cbkb import CBKB, LabSOP
from homomics_lab.projects import ProjectExporter, ProjectImporter


@pytest.fixture
def test_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return tmp_path


@pytest.fixture
def exporter(test_data_dir):
    return ProjectExporter("test_proj")


@pytest.fixture
def importer(test_data_dir):
    return ProjectImporter()


class TestRichConfigExport:
    def test_export_creates_valid_zip(self, exporter, test_data_dir):
        archive = exporter.export_to(test_data_dir / "out.homomics")
        assert archive.exists()
        assert zipfile.is_zipfile(archive)
        with zipfile.ZipFile(archive) as zf:
            assert "project.json" in zf.namelist()
            assert "config.json" in zf.namelist()

    def test_config_contains_reproducibility_keys(self, exporter, test_data_dir):
        archive = exporter.export_to(test_data_dir / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            config = json.loads(zf.read("config.json"))

        assert config["project_id"] == "test_proj"
        assert "exported_at" in config
        assert "exporter_version" in config
        assert "analysis_state" in config
        assert "skill_versions" in config
        assert "environment" in config
        assert "settings_snapshot" in config
        assert "sop_references" in config

    def test_analysis_state_exported(self, exporter, test_data_dir):
        cbkb = CBKB(test_data_dir)
        state = ProjectState(
            project_id="test_proj",
            completed_phases=["QC"],
            last_skill_id="scanpy_qc",
        )
        ProjectStateManager(cbkb).save(state)

        archive = exporter.export_to(test_data_dir / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            config = json.loads(zf.read("config.json"))

        assert config["analysis_state"]["completed_phases"] == ["QC"]
        assert config["analysis_state"]["last_skill_id"] == "scanpy_qc"

    def test_skill_versions_exported(self, exporter, test_data_dir):
        skill_store_dir = test_data_dir / "skill_store"
        skill_store_dir.mkdir(parents=True)
        skills = {
            "default:qc": {
                "id": "qc",
                "namespace": "default",
                "version": "1.2.3",
                "source": "builtin",
                "trusted": True,
                "enabled": True,
            }
        }
        (skill_store_dir / "skills.json").write_text(json.dumps(skills), encoding="utf-8")

        archive = exporter.export_to(test_data_dir / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            config = json.loads(zf.read("config.json"))

        assert len(config["skill_versions"]) == 1
        entry = config["skill_versions"][0]
        assert entry["id"] == "qc"
        assert entry["namespace"] == "default"
        assert entry["version"] == "1.2.3"
        assert entry["source"] == "builtin"
        assert entry["trusted"] is True
        assert entry["enabled"] is True

    def test_skill_versions_graceful_when_missing(self, exporter, test_data_dir):
        archive = exporter.export_to(test_data_dir / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            config = json.loads(zf.read("config.json"))
        assert config["skill_versions"] == []

    def test_sop_references_exported(self, exporter, test_data_dir):
        cbkb = CBKB(test_data_dir)
        cbkb.create_sop(
            LabSOP(
                id="sop_qc_001",
                name="QC SOP",
                category="qc",
                template={"steps": []},
                derived_from_bundle_ids=["bundle_1"],
            )
        )

        archive = exporter.export_to(test_data_dir / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            config = json.loads(zf.read("config.json"))

        assert "sop_qc_001" in config["sop_references"]

    def test_settings_snapshot_safe(self, exporter, test_data_dir):
        archive = exporter.export_to(test_data_dir / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            config = json.loads(zf.read("config.json"))

        snapshot = config["settings_snapshot"]
        assert snapshot["storage_backend"] == settings.storage_backend
        assert snapshot["queue_backend"] == settings.queue_backend
        assert "database_url_driver" in snapshot
        for secret_key in ("api_key", "jwt_secret_key", "storage_s3_secret_key"):
            assert secret_key not in snapshot

    def test_environment_has_required_keys(self, exporter, test_data_dir):
        archive = exporter.export_to(test_data_dir / "out.homomics")
        with zipfile.ZipFile(archive) as zf:
            config = json.loads(zf.read("config.json"))

        env = config["environment"]
        assert env["python_version"]
        assert env["app_version"] == "0.5.0"
        assert "dependencies" in env
        for dep in ("scanpy", "anndata", "pandas", "numpy", "sqlalchemy"):
            assert dep in env["dependencies"]


class TestProjectImporterConfigValidation:
    def test_import_requires_config_json(self, exporter, importer, test_data_dir):
        archive = exporter.export_to(test_data_dir / "out.homomics")
        no_config_archive = test_data_dir / "no_config.homomics"

        with zipfile.ZipFile(archive, "r") as src, zipfile.ZipFile(
            no_config_archive, "w"
        ) as dst:
            for item in src.namelist():
                if item != "config.json":
                    dst.writestr(item, src.read(item))

        with pytest.raises(ValueError, match="config.json"):
            importer.import_from(no_config_archive)

    def test_import_writes_config_to_project_dir(self, exporter, importer, test_data_dir):
        archive = exporter.export_to(test_data_dir / "out.homomics")
        imported_id = importer.import_from(archive)

        config_path = test_data_dir / "projects" / imported_id / "config.json"
        assert config_path.exists()
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["project_id"] == "test_proj"

    def test_import_warns_on_missing_reproducibility_fields(
        self, exporter, importer, test_data_dir, caplog
    ):
        archive = exporter.export_to(test_data_dir / "out.homomics")

        # Build a minimal archive with config.json stripped of rich fields.
        stripped_archive = test_data_dir / "stripped.homomics"
        with zipfile.ZipFile(archive, "r") as src, zipfile.ZipFile(
            stripped_archive, "w"
        ) as dst:
            for item in src.namelist():
                if item == "config.json":
                    config = json.loads(src.read("config.json"))
                    minimal_config = {
                        "project_id": config["project_id"],
                        "data_dir": config["data_dir"],
                    }
                    dst.writestr(item, json.dumps(minimal_config))
                else:
                    dst.writestr(item, src.read(item))

        with caplog.at_level("WARNING"):
            importer.import_from(stripped_archive)

        assert any(
            field in caplog.text
            for field in ("analysis_state", "skill_versions", "environment")
        )
