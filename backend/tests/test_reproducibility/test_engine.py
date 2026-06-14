"""Tests for ReproducibilityEngine."""

from unittest.mock import patch

from homomics_lab.reproducibility.bundle import EnvironmentLock, ReproducibilityBundle
from homomics_lab.reproducibility.engine import ReproducibilityEngine
from homomics_lab.workspace.manager import WorkspaceManager


def _fast_capture() -> EnvironmentLock:
    return EnvironmentLock(
        python_version="3.12.0",
        pip_freeze="mock-pkg==1.0\n",
        conda_env_export="",
        system_info={"platform": "linux", "machine": "x86_64"},
    )


class TestReproducibilityEngine:
    def test_start_analysis(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        with patch.object(engine, "_capture_environment", _fast_capture):
            engine.start_analysis(project_id="proj_1", random_seed=42)

        assert engine._bundle is not None
        assert engine._bundle.project_id == "proj_1"
        assert engine._bundle.random_seed == 42
        assert engine._bundle.environment_lock.python_version != ""

    def test_record_plan(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        with patch.object(engine, "_capture_environment", _fast_capture):
            engine.start_analysis(project_id="proj_1")

        engine.record_plan(
            task_tree={"tasks": [{"id": "qc_1"}]},
            plan_context={"plan_engine_version": "0.3.0", "llm_model": "gpt-4"},
        )

        assert engine._bundle.execution_snapshot is not None
        assert engine._bundle.execution_snapshot.plan_version == "0.3.0"

    def test_record_plan_with_plan_id(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        with patch.object(engine, "_capture_environment", _fast_capture):
            engine.start_analysis(project_id="proj_1")

        engine.record_plan(
            task_tree={"tasks": [{"id": "qc_1"}]},
            plan_context={"plan_engine_version": "0.5.0"},
            plan_id="plan_123",
            plan_result={"phases": [{"phase_type": "qc"}]},
        )

        assert engine._bundle.execution_snapshot.plan_id == "plan_123"
        assert engine._bundle.execution_snapshot.plan_result is not None
        assert (
            engine._bundle.execution_snapshot.plan_result["phases"][0]["phase_type"]
            == "qc"
        )

    def test_record_code(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        with patch.object(engine, "_capture_environment", _fast_capture):
            engine.start_analysis(project_id="proj_1")

        engine.record_code(
            phase="qc",
            code="import scanpy as sc\nadata = sc.read('file.h5ad')",
        )

        assert len(engine._bundle.agent_code_archive) == 1
        assert engine._bundle.agent_code_archive[0].phase == "qc"
        assert "scanpy" in engine._bundle.agent_code_archive[0].code

    def test_record_hitl_decision(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        with patch.object(engine, "_capture_environment", _fast_capture):
            engine.start_analysis(project_id="proj_1")

        engine.record_hitl_decision(
            checkpoint_id="cp_1",
            choice="custom",
            parameters={"resolution": 0.8},
        )

        assert len(engine._bundle.hitl_decisions) == 1
        assert engine._bundle.hitl_decisions[0].choice == "custom"

    def test_finalize_saves_bundle(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        with patch.object(engine, "_capture_environment", _fast_capture):
            engine.start_analysis(project_id="proj_1", random_seed=123)
        engine.record_code(phase="qc", code="print('hello')")

        engine.finalize()

        # Verify bundle was saved to workspace
        bundle_path = ws.get_path(".metadata/reproducibility_bundle.json")
        assert bundle_path.exists()

        # Verify loaded bundle matches
        loaded = ReproducibilityBundle.load(bundle_path)
        assert loaded.project_id == "proj_1"
        assert loaded.random_seed == 123
        assert len(loaded.agent_code_archive) == 1

    def test_bundle_roundtrip_json(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        with patch.object(engine, "_capture_environment", _fast_capture):
            engine.start_analysis(project_id="proj_1")
        engine.record_code(phase="test", code="x = 1")
        bundle = engine.finalize()

        # Roundtrip through JSON
        json_str = bundle.to_json()
        restored = ReproducibilityBundle.from_json(json_str)

        assert restored.project_id == bundle.project_id
        assert restored.random_seed == bundle.random_seed
        assert len(restored.agent_code_archive) == len(bundle.agent_code_archive)

    def test_environment_capture(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        engine = ReproducibilityEngine(ws)
        env = engine._capture_environment()

        assert env.python_version != ""
        assert "platform" in env.system_info
