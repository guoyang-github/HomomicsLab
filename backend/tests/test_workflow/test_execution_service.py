"""Tests for WorkflowExecutionService backend routing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homomics_lab.agent.plan.models import DataState as PlanDataState, Phase, PlanResult
from homomics_lab.plan.models import Plan
from homomics_lab.tasks.models import TaskNode, TaskStatus
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.workflow.execution_service import WorkflowExecutionService
from homomics_lab.workflow.models import WorkflowArtifact, WorkflowResult


@pytest.fixture
def plan(tmp_path) -> Plan:
    """A simple multi-phase plan with a minimal task tree."""
    phases = [
        Phase(phase_type="qc", required=True, description="Quality control"),
        Phase(phase_type="normalize", required=True, description="Normalize"),
        Phase(phase_type="cluster", required=True, description="Cluster"),
        Phase(phase_type="visualize", required=True, description="Visualize"),
    ]
    plan_result = PlanResult(
        phases=phases,
        strategy_name="single_cell_standard",
        is_fallback=False,
        data_state=PlanDataState(),
    )
    tasks = [
        TaskNode(id="t1", name="qc", description="QC", phase="qc", status=TaskStatus.PENDING),
        TaskNode(id="t2", name="normalize", description="Normalize", phase="normalize", status=TaskStatus.PENDING),
        TaskNode(id="t3", name="cluster", description="Cluster", phase="cluster", status=TaskStatus.PENDING),
        TaskNode(id="t4", name="visualize", description="Visualize", phase="visualize", status=TaskStatus.PENDING),
    ]
    return Plan(
        plan_id="plan_test",
        session_id="sess_test",
        project_id="proj_test",
        intent_analysis_type="single_cell_analysis",
        plan_result=plan_result,
        task_tree=TaskTree(tasks=tasks),
    )


@pytest.fixture
def service() -> WorkflowExecutionService:
    return WorkflowExecutionService()


class TestBackendSelection:
    @pytest.mark.asyncio
    async def test_routes_to_local_when_nextflow_unavailable(self, service, plan, monkeypatch):
        monkeypatch.setattr("homomics_lab.hpc.scheduler.NextflowRunner.is_available", lambda: False)
        monkeypatch.setattr("homomics_lab.hpc.scheduler.SlurmScheduler.is_available", lambda: False)

        orchestrator = MagicMock()
        orchestrator.run_tree = AsyncMock(return_value={"t1": {"success": True}})
        service.orchestrator = orchestrator

        result = await service.execute(plan, project_id="proj_test")

        assert result.backend == "local"
        assert result.success is True
        orchestrator.run_tree.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routes_to_nextflow_when_available(self, service, plan, monkeypatch, tmp_path):
        monkeypatch.setattr("homomics_lab.hpc.scheduler.NextflowRunner.is_available", lambda: True)
        monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
        monkeypatch.setattr("homomics_lab.config.settings.workflow_nextflow_min_phases", 3)

        def _make_nextflow_result(*args, **kwargs):
            for task in plan.task_tree.tasks:
                task.status = TaskStatus.COMPLETED
            return WorkflowResult(
                success=True,
                backend="nextflow",
                task_tree=plan.task_tree,
                artifacts=[WorkflowArtifact(path=str(tmp_path / "main.nf"), artifact_type="log")],
            )

        with patch.object(
            service.__class__,
            "_execute_nextflow",
            new=AsyncMock(side_effect=_make_nextflow_result),
        ):
            result = await service.execute(plan, project_id="proj_test")

        assert result.backend == "nextflow"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_nextflow_failure_falls_back_to_local(self, service, plan, monkeypatch):
        monkeypatch.setattr("homomics_lab.hpc.scheduler.NextflowRunner.is_available", lambda: True)
        monkeypatch.setattr("homomics_lab.config.settings.workflow_nextflow_min_phases", 3)

        with patch.object(
            service.__class__,
            "_execute_nextflow",
            new=AsyncMock(side_effect=RuntimeError("nextflow not installed")),
        ):
            orchestrator = MagicMock()
            orchestrator.run_tree = AsyncMock(return_value={"t1": {"success": True}})
            service.orchestrator = orchestrator

            result = await service.execute(plan, project_id="proj_test")

        assert result.backend == "local"
        assert result.success is True
        orchestrator.run_tree.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_nextflow_result_failure_falls_back_to_local(self, service, plan, monkeypatch):
        """A Nextflow run that returns a failed WorkflowResult also triggers local fallback."""
        monkeypatch.setattr("homomics_lab.hpc.scheduler.NextflowRunner.is_available", lambda: True)
        monkeypatch.setattr("homomics_lab.config.settings.workflow_nextflow_min_phases", 3)

        with patch.object(
            service.__class__,
            "_execute_nextflow",
            new=AsyncMock(
                return_value=WorkflowResult(
                    success=False,
                    backend="nextflow",
                    task_tree=plan.task_tree,
                    error_message="container not available",
                )
            ),
        ):
            orchestrator = MagicMock()
            orchestrator.run_tree = AsyncMock(return_value={"t1": {"success": True}})
            service.orchestrator = orchestrator

            result = await service.execute(plan, project_id="proj_test")

        assert result.backend == "local"
        assert result.success is True
        orchestrator.run_tree.assert_awaited_once()


class TestLocalExecution:
    @pytest.mark.asyncio
    async def test_failed_task_marks_result_unsuccessful(self, service, plan, monkeypatch):
        monkeypatch.setattr("homomics_lab.hpc.scheduler.NextflowRunner.is_available", lambda: False)

        orchestrator = MagicMock()
        orchestrator.run_tree = AsyncMock(return_value={})
        service.orchestrator = orchestrator

        # Mark a task as failed.
        plan.task_tree.tasks[0].status = TaskStatus.FAILED
        result = await service.execute(plan, project_id="proj_test")

        assert result.backend == "local"
        assert result.success is False


class TestNextflowHelpers:
    def test_build_data_state_extracts_sample_count(self, service, plan):
        plan.plan_result.phases[0].parameters["n_samples"] = 42
        data_state = service._build_data_state(plan.plan_result, "proj_test")
        assert data_state.n_samples == 42

    def test_collect_artifacts_from_outdir(self, service, tmp_path):
        outdir = tmp_path / "results"
        outdir.mkdir()
        (outdir / "plot.png").write_text("png")
        (outdir / "table.csv").write_text("csv")

        result = {"outdir": str(outdir)}
        inputs = {"outdir": str(outdir)}
        artifacts = service._collect_artifacts(result, inputs)

        paths = {a.path for a in artifacts}
        assert any("plot.png" in p for p in paths)
        assert any("table.csv" in p for p in paths)
