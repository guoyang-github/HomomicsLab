"""Tests for StabilityGuard L2: VersionLocker + RegressionTester."""

import json
from pathlib import Path

import pytest

from homomics_lab.skills.models import (
    SkillDefinition,
    SkillInputSchema,
    SkillOutputSchema,
    SkillRuntime,
)
from homomics_lab.stability.regression_tester import (
    RegressionTester,
    RegressionResult,
    TestBaseline,
    _output_signature,
)
from homomics_lab.stability.version_locker import (
    LockVerificationResult,
    VersionLock,
    VersionLocker,
)


@pytest.fixture
def tmp_workspace(tmp_path):
    return tmp_path


@pytest.fixture
def fake_skill():
    return SkillDefinition(
        id="test.normalizer",
        name="Normalizer",
        version="1.2.3",
        category="preprocessing",
        runtime=SkillRuntime(type="python"),
        input_schema=SkillInputSchema(),
        output_schema=SkillOutputSchema(),
        metadata={"scripts_dir": "/tmp/fake_scripts"},
    )


@pytest.fixture
def fake_registry(fake_skill):
    class FakeRegistry:
        def list_all(self):
            return [fake_skill]

        def get(self, skill_id):
            if skill_id == fake_skill.id:
                return fake_skill
            return None

    return FakeRegistry()


class TestVersionLocker:

    def test_init(self, tmp_workspace):
        locker = VersionLocker(tmp_workspace)
        assert locker.workspace_dir == tmp_workspace

    def test_lock_project(self, tmp_workspace, fake_registry):
        locker = VersionLocker(tmp_workspace)
        lock = locker.lock_project("proj-1", fake_registry)

        assert lock.project_id == "proj-1"
        assert "test.normalizer" in lock.skills
        assert lock.skills["test.normalizer"] == "1.2.3"
        assert lock.environment != ""
        assert lock.python_version != ""

    def test_lock_saved_to_disk(self, tmp_workspace, fake_registry):
        locker = VersionLocker(tmp_workspace)
        locker.lock_project("proj-1", fake_registry)

        lock_path = tmp_workspace / ".metadata" / "version.lock"
        assert lock_path.exists()

        data = json.loads(lock_path.read_text())
        assert data["project_id"] == "proj-1"
        assert data["skills"]["test.normalizer"] == "1.2.3"

    def test_verify_compatible(self, tmp_workspace, fake_registry):
        locker = VersionLocker(tmp_workspace)
        locker.lock_project("proj-1", fake_registry)

        result = locker.verify(fake_registry)
        assert result.compatible is True
        assert len(result.version_mismatches) == 0

    def test_verify_version_mismatch(self, tmp_workspace, fake_registry, fake_skill):
        locker = VersionLocker(tmp_workspace)
        locker.lock_project("proj-1", fake_registry)

        # Bump version
        fake_skill.version = "1.3.0"

        result = locker.verify(fake_registry)
        assert result.compatible is False
        assert len(result.version_mismatches) == 1
        assert "1.2.3" in result.version_mismatches[0]
        assert "1.3.0" in result.version_mismatches[0]

    def test_verify_missing_skill(self, tmp_workspace, fake_registry):
        locker = VersionLocker(tmp_workspace)
        locker.lock_project("proj-1", fake_registry)

        # Empty registry
        class EmptyRegistry:
            def list_all(self):
                return []

            def get(self, skill_id):
                return None

        result = locker.verify(EmptyRegistry())
        assert result.compatible is False
        assert "test.normalizer" in result.missing_skills

    def test_verify_new_skill(self, tmp_workspace, fake_registry, fake_skill):
        locker = VersionLocker(tmp_workspace)
        locker.lock_project("proj-1", fake_registry)

        # Add a new skill
        new_skill = SkillDefinition(
            id="test.clusterer",
            name="Clusterer",
            version="2.0.0",
            category="analysis",
            runtime=SkillRuntime(type="python"),
            input_schema=SkillInputSchema(),
            output_schema=SkillOutputSchema(),
            metadata={},
        )

        class ExpandedRegistry:
            def list_all(self):
                return [fake_skill, new_skill]

            def get(self, skill_id):
                return {fake_skill.id: fake_skill, new_skill.id: new_skill}.get(skill_id)

        result = locker.verify(ExpandedRegistry())
        assert result.compatible is False
        assert any("test.clusterer" in m for m in result.version_mismatches)

    def test_load_lock_roundtrip(self, tmp_workspace, fake_registry):
        locker = VersionLocker(tmp_workspace)
        original = locker.lock_project("proj-1", fake_registry)

        loaded = locker._load_lock()
        assert loaded is not None
        assert loaded.project_id == original.project_id
        assert loaded.skills == original.skills
        assert loaded.environment == original.environment

    def test_no_lock_returns_none(self, tmp_workspace):
        locker = VersionLocker(tmp_workspace)
        assert locker._load_lock() is None

    def test_checksums_recorded(self, tmp_workspace, fake_registry):
        locker = VersionLocker(tmp_workspace)
        lock = locker.lock_project("proj-1", fake_registry)

        # scripts_dir doesn't exist so checksum is hash of empty
        assert "test.normalizer" in lock.skill_checksums
        assert len(lock.skill_checksums["test.normalizer"]) == 16


class TestRegressionTester:

    def test_init(self, tmp_workspace):
        rt = RegressionTester(tmp_workspace)
        assert rt.workspace_dir == tmp_workspace
        assert rt.baseline_dir.exists()

    def test_record_baseline(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        output = {"n_cells": 1000, "filtered": 5, "pass": True}

        baseline = rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={"min_genes": 200},
            actual_output=output,
            metadata={"note": "v1 test"},
        )

        assert baseline.skill_id == "test.normalizer"
        assert baseline.test_case_id == "basic_run"
        assert baseline.expected_keys == list(output.keys())
        assert baseline.expected_output_signature == _output_signature(output)

    def test_baseline_saved_to_disk(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={"min_genes": 200},
            actual_output={"n_cells": 1000},
        )

        path = tmp_workspace / ".metadata" / "regression_baselines" / "test.normalizer__basic_run.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["skill_id"] == "test.normalizer"

    def test_load_baseline(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={"min_genes": 200},
            actual_output={"n_cells": 1000},
        )

        loaded = rt.load_baseline("test.normalizer", "basic_run")
        assert loaded is not None
        assert loaded.skill_id == "test.normalizer"

    def test_load_baseline_missing(self, tmp_workspace):
        rt = RegressionTester(tmp_workspace)
        assert rt.load_baseline("x", "y") is None

    def test_test_against_baseline_pass(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        output = {"n_cells": 1000, "filtered": 5, "pass": True}
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={},
            actual_output=output,
        )

        result = rt.test_against_baseline(
            skill_id="test.normalizer",
            test_case_id="basic_run",
            actual_output=output,
        )

        assert result.passed is True
        assert result.signature_match is True
        assert len(result.missing_keys) == 0
        assert len(result.extra_keys) == 0

    def test_test_against_baseline_missing_keys(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={},
            actual_output={"n_cells": 1000, "filtered": 5},
        )

        result = rt.test_against_baseline(
            skill_id="test.normalizer",
            test_case_id="basic_run",
            actual_output={"n_cells": 1000},  # missing "filtered"
        )

        assert result.passed is False
        assert "filtered" in result.missing_keys

    def test_test_against_baseline_extra_keys_ok(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={},
            actual_output={"n_cells": 1000},
        )

        result = rt.test_against_baseline(
            skill_id="test.normalizer",
            test_case_id="basic_run",
            actual_output={"n_cells": 1000, "new_field": "ok"},
            exact_signature=False,
        )

        # Extra keys don't fail the test
        assert result.passed is True
        assert "new_field" in result.extra_keys

    def test_test_against_baseline_signature_mismatch(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={},
            actual_output={"n_cells": 1000},
        )

        result = rt.test_against_baseline(
            skill_id="test.normalizer",
            test_case_id="basic_run",
            actual_output={"n_cells": 999},  # value changed
            exact_signature=True,
        )

        assert result.passed is False
        assert result.signature_match is False

    def test_test_no_baseline(self, tmp_workspace):
        rt = RegressionTester(tmp_workspace)
        result = rt.test_against_baseline(
            skill_id="x",
            test_case_id="y",
            actual_output={},
        )
        assert result.passed is False
        assert result.error == "No baseline found"

    def test_list_baselines(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(skill=fake_skill, test_case_id="run_a", test_input={}, actual_output={})
        rt.record_baseline(skill=fake_skill, test_case_id="run_b", test_input={}, actual_output={})

        baselines = rt.list_baselines()
        assert len(baselines) == 2
        assert ("test.normalizer", "run_a") in baselines
        assert ("test.normalizer", "run_b") in baselines

        filtered = rt.list_baselines(skill_id="test.normalizer")
        assert len(filtered) == 2

    def test_output_signature_stability(self):
        """Signature should be stable for identical outputs."""
        out = {"a": 1, "b": "hello", "c": [1, 2, 3]}
        sig1 = _output_signature(out)
        sig2 = _output_signature(out)
        assert sig1 == sig2
        assert len(sig1) == 16

    def test_output_signature_change(self):
        """Signature should change when values change."""
        sig1 = _output_signature({"a": 1})
        sig2 = _output_signature({"a": 2})
        assert sig1 != sig2

    def test_exact_signature_false_allows_drift(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={},
            actual_output={"n_cells": 1000},
        )

        result = rt.test_against_baseline(
            skill_id="test.normalizer",
            test_case_id="basic_run",
            actual_output={"n_cells": 999},  # value changed
            exact_signature=False,
        )

        assert result.passed is True
        assert result.signature_match is False  # still reports mismatch

    def test_required_keys_override(self, tmp_workspace, fake_skill):
        rt = RegressionTester(tmp_workspace)
        rt.record_baseline(
            skill=fake_skill,
            test_case_id="basic_run",
            test_input={},
            actual_output={"n_cells": 1000},
        )

        result = rt.test_against_baseline(
            skill_id="test.normalizer",
            test_case_id="basic_run",
            actual_output={"n_cells": 1000},
            required_keys=["n_cells", "must_exist"],
        )

        assert result.passed is False
        assert "must_exist" in result.missing_keys


class TestVersionLockDataclass:

    def test_creation(self):
        lock = VersionLock(
            project_id="p1",
            locked_at="2024-01-01T00:00:00+00:00",
            skills={"a": "1.0"},
            skill_checksums={"a": "abc123"},
            environment="pip freeze output",
            python_version="3.12",
            homomics_version="0.3.0",
        )
        assert lock.project_id == "p1"


class TestRegressionResultDataclass:

    def test_creation(self):
        result = RegressionResult(
            skill_id="a",
            test_case_id="b",
            passed=True,
        )
        assert result.passed is True
