"""Tests for SkillStore."""

import zipfile
from pathlib import Path

import pytest

from homomics_lab.skills.skill_store import SkillStore, SkillStoreError


@pytest.fixture
def sample_skill_dir(tmp_path):
    """Create a minimal valid skill directory."""
    skill_dir = tmp_path / "bio-test-qc"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""\
---
name: bio-test-qc
description: Test QC skill.
version: 1.0.0
tool_type: python
primary_tool: test
keywords: ["test", "qc"]
category: test
inputs:
  adata_path:
    type: string
    required: true
outputs:
  output_path:
    type: string
---

# Test QC

Test skill.
""")
    scripts = skill_dir / "scripts" / "python"
    scripts.mkdir(parents=True)
    (scripts / "run.py").write_text("print('ok')\n")
    return skill_dir


@pytest.fixture
def store(tmp_path):
    return SkillStore(
        store_dir=tmp_path / "skill_store",
        skills_dir=tmp_path / "skills",
    )


class TestSkillStoreImport:
    def test_import_local_skill(self, store, sample_skill_dir):
        skill = store.import_skill(str(sample_skill_dir), namespace="test")

        assert skill.id == "bio-test-qc"
        assert skill.metadata["namespace"] == "test"
        assert store.registry.get("bio-test-qc") is not None
        meta = store.get_meta("bio-test-qc", "test")
        assert meta["enabled"] is True

    def test_import_without_enable(self, store, sample_skill_dir):
        skill = store.import_skill(str(sample_skill_dir), enable=False)

        assert skill.id == "bio-test-qc"
        assert store.registry.get("bio-test-qc") is None
        meta = store.get_meta("bio-test-qc", "default")
        assert meta["enabled"] is False

    def test_import_invalid_source(self, store):
        with pytest.raises(SkillStoreError):
            store.import_skill("/nonexistent/path")

    def test_disable_and_enable(self, store, sample_skill_dir):
        store.import_skill(str(sample_skill_dir))
        store.disable_skill("bio-test-qc")

        assert store.registry.get("bio-test-qc") is None
        assert store.get_meta("bio-test-qc", "default")["enabled"] is False

        skill = store.enable_skill("bio-test-qc")
        assert skill is not None
        assert store.registry.get("bio-test-qc") is not None


class TestSkillStoreQuery:
    def test_list_skills(self, store, sample_skill_dir):
        store.import_skill(str(sample_skill_dir), namespace="ns1")
        store.import_skill(str(sample_skill_dir), namespace="ns2", enable=False)

        # Default listing includes both enabled and disabled, de-duplicated by id.
        all_skills = store.list_skills()
        assert len(all_skills) == 1
        assert all_skills[0].metadata.get("namespace") == "ns1"

        ns1 = store.list_skills(namespace="ns1")
        assert len(ns1) == 1

        # Disabled skills are returned unless ``enabled_only=True``.
        ns2 = store.list_skills(namespace="ns2")
        assert len(ns2) == 1
        assert ns2[0].metadata.get("enabled") is False

        enabled_only = store.list_skills(namespace="ns2", enabled_only=True)
        assert len(enabled_only) == 0

    def test_get_skill_namespace_fallback(self, store, sample_skill_dir):
        store.import_skill(str(sample_skill_dir), namespace="custom")

        skill = store.get_skill("bio-test-qc")
        assert skill is not None
        assert skill.metadata["namespace"] == "custom"


class TestSkillStoreValidation:
    def test_validate_valid_skill(self, sample_skill_dir):
        report = SkillStore.validate_skill(sample_skill_dir)
        assert report.valid is True
        assert len(report.errors) == 0

    def test_validate_missing_skill_md(self, tmp_path):
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        report = SkillStore.validate_skill(bad_dir)
        assert report.valid is False
        assert any("SKILL.md" in e for e in report.errors)

    def test_validate_declarative_skill_without_scripts_is_valid(self, tmp_path):
        skill_dir = tmp_path / "declarative_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            """---
name: declarative-skill
tool_type: workflow
description: A declarative workflow skill with no scripts.
---

# Instructions
Generate a Nextflow pipeline.
""",
            encoding="utf-8",
        )
        report = SkillStore.validate_skill(skill_dir)
        assert report.valid is True
        assert not any("No scripts/" in w for w in report.warnings)


class TestSkillStoreVersionLock:
    def test_lock_and_save(self, store, sample_skill_dir, tmp_path):
        store.import_skill(str(sample_skill_dir), namespace="default")
        lock_path = tmp_path / "homomics.lock"
        lock = store.save_lock_file("proj_a", lock_path)

        assert lock.project_id == "proj_a"
        assert "default/bio-test-qc" in lock.skills
        assert lock_path.exists()

        loaded = store.load_lock_file(lock_path)
        assert loaded.skills == lock.skills

    def test_verify_lock_pass(self, store, sample_skill_dir):
        store.import_skill(str(sample_skill_dir))
        lock = store.lock_versions("proj_a")
        report = store.verify_lock(lock)
        assert report.valid is True

    def test_verify_lock_fail_missing(self, store, sample_skill_dir):
        store.import_skill(str(sample_skill_dir))
        lock = store.lock_versions("proj_a")
        store.remove_skill("bio-test-qc")
        report = store.verify_lock(lock)
        assert report.valid is False

    def test_verify_lock_fail_version(self, store, sample_skill_dir):
        store.import_skill(str(sample_skill_dir))
        lock = store.lock_versions("proj_a")
        # Simulate version mismatch by mutating lock
        lock.skills["default/bio-test-qc"] = "9.9.9"
        report = store.verify_lock(lock)
        assert report.valid is False


class TestSkillStoreDropin:
    def test_register_dropin_does_not_copy(self, store, sample_skill_dir):
        skill = store.register_dropin(sample_skill_dir, namespace="user")

        assert skill.id == "bio-test-qc"
        assert skill.metadata["source"] == "dropin"
        assert skill.metadata["trusted"] is False
        assert store.get_meta("bio-test-qc", "user")["source_dir"] == str(
            sample_skill_dir.resolve()
        )

    def test_remove_skill_deletes_managed_dir(self, store, sample_skill_dir):
        skill = store.import_skill(str(sample_skill_dir))
        target_dir = Path(skill.metadata["source_dir"])
        assert target_dir.exists()

        store.remove_skill("bio-test-qc")

        assert not target_dir.exists()
        assert store.get_meta("bio-test-qc") is None


class TestSkillStoreZipImport:
    def test_import_from_zip(self, store, sample_skill_dir, tmp_path):
        zip_path = tmp_path / "skill.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for file in sample_skill_dir.rglob("*"):
                zf.write(file, arcname=file.relative_to(sample_skill_dir.parent))

        skill = store.import_skill(str(zip_path))
        assert skill.id == "bio-test-qc"
