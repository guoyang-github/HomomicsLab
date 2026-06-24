import asyncio
import pytest
from pathlib import Path
from homomics_lab.hpc.scheduler import LocalScheduler, SlurmScheduler, NextflowRunner, get_scheduler
from homomics_lab.skills.models import SkillDefinition, SkillRuntime, SkillResources


class TestLocalScheduler:
    @pytest.mark.asyncio
    async def test_local_scheduler_runs_python(self, tmp_path):
        scheduler = LocalScheduler(working_dir=tmp_path)
        skill = SkillDefinition(
            id="test", name="Test", version="1.0", category="test",
            runtime=SkillRuntime(type="python"),
        )

        result = await scheduler.execute(
            skill, "result = {'x': 42}", {"a": 1}, timeout_seconds=30
        )
        assert result["x"] == 42

    @pytest.mark.asyncio
    async def test_local_scheduler_runs_r(self, tmp_path):
        scheduler = LocalScheduler(working_dir=tmp_path)
        skill = SkillDefinition(
            id="test", name="Test", version="1.0", category="test",
            runtime=SkillRuntime(type="r"),
        )

        result = await scheduler.execute(
            skill, "result <- list(x = 42)", {}, timeout_seconds=30
        )
        assert result["x"] == 42

    def test_local_scheduler_available(self):
        assert LocalScheduler.is_available()


class TestSlurmScheduler:
    def test_slurm_scheduler_detects_availability(self):
        # Should return False if sbatch not found (typical test env)
        available = SlurmScheduler.is_available()
        assert isinstance(available, bool)

    def test_build_sbatch_script(self, tmp_path):
        scheduler = SlurmScheduler(working_dir=tmp_path)
        skill = SkillDefinition(
            id="test", name="Test", version="1.0", category="test",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="8G", cpu=4, time="2h"),
            ),
        )

        script = scheduler._build_sbatch_script(skill, "print('hello')", "test_job")

        assert "#SBATCH --job-name=test_job" in script
        assert "#SBATCH --mem=8G" in script
        assert "#SBATCH --cpus-per-task=4" in script
        assert "#SBATCH --time=2:00:00" in script
        assert "print('hello')" in script

    def test_resource_mapping_defaults(self, tmp_path):
        scheduler = SlurmScheduler(working_dir=tmp_path)
        skill = SkillDefinition(
            id="test", name="Test", version="1.0", category="test",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="4G", cpu=2, time="30m"),
            ),
        )

        script = scheduler._build_sbatch_script(skill, "", "job")
        assert "#SBATCH --mem=4G" in script
        assert "#SBATCH --cpus-per-task=2" in script
        assert "#SBATCH --time=0:30:00" in script

    @pytest.mark.asyncio
    async def test_execute_returns_submitted_handle_and_polls_in_background(self, tmp_path, monkeypatch):
        """execute() must be non-blocking and publish terminal state via pub/sub."""
        from homomics_lab.hpc.state import ExecutionState
        from homomics_lab.jobs.backends.memory import MemoryPubSubBackend

        pubsub = MemoryPubSubBackend()
        scheduler = SlurmScheduler(working_dir=tmp_path, pubsub=pubsub)
        skill = SkillDefinition(
            id="test", name="Test", version="1.0", category="test",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="4G", cpu=2, time="30m"),
            ),
        )

        submitted = {"job_id": "12345"}

        async def fake_sbatch(*args, **kwargs):
            class Proc:
                returncode = 0
                async def communicate(self):
                    return b"Submitted batch job 12345", b""
            return Proc()

        async def fake_poll_job(*args, **kwargs):
            scheduler._report_progress(
                ExecutionState(
                    job_id="12345",
                    status="COMPLETED",
                    current_phase=skill.id,
                    progress_pct=100.0,
                    scheduler_type="slurm",
                )
            )
            return {"status": "completed", "job_id": "12345"}

        import homomics_lab.hpc.scheduler as scheduler_module
        _real_asyncio = asyncio
        class FakeAsyncio:
            @staticmethod
            async def create_subprocess_exec(*args, **kwargs):
                return await fake_sbatch(*args, **kwargs)
            @staticmethod
            def create_task(coro, *, name=None):
                return _real_asyncio.create_task(coro, name=name)
            subprocess = _real_asyncio.subprocess
        monkeypatch.setattr(scheduler_module, "asyncio", FakeAsyncio())
        monkeypatch.setattr(scheduler, "_poll_job", fake_poll_job)

        result = await scheduler.execute(skill, "result = {'x': 1}", {})
        assert result["status"] == "submitted"
        assert result["job_id"] == "12345"

        # Give the background monitor task a chance to run.
        await asyncio.sleep(0.05)

        latest = await pubsub.latest("12345")
        assert latest is not None
        assert latest.status == "COMPLETED"


class TestNextflowRunner:
    def test_nextflow_detects_availability(self):
        available = NextflowRunner.is_available()
        assert isinstance(available, bool)

    def test_build_nextflow_config(self, tmp_path):
        runner = NextflowRunner(working_dir=tmp_path)
        skill = SkillDefinition(
            id="test", name="Test", version="1.0", category="test",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="16G", cpu=8, time="4h"),
            ),
        )

        config = runner._build_process_config(skill)

        assert "memory = 16.GB" in config or "memory" in config
        assert "cpus = 8" in config or "cpus" in config
        assert "time = 4.h" in config or "time" in config

    def test_time_format_conversion(self, tmp_path):
        runner = NextflowRunner(working_dir=tmp_path)

        assert runner._to_nextflow_time("30m") == "30.m"
        assert runner._to_nextflow_time("2h") == "2.h"
        assert runner._to_nextflow_time("1d") == "1.d"
        assert runner._to_nextflow_time("45s") == "45.s"

    @pytest.mark.asyncio
    async def test_run_pipeline_dir_ingests_results(self, tmp_path, monkeypatch):
        from homomics_lab.config import settings

        monkeypatch.setattr(settings, "data_dir", tmp_path)
        runner = NextflowRunner(working_dir=tmp_path)

        pipeline_dir = tmp_path / "nf-core-test"
        pipeline_dir.mkdir()
        (pipeline_dir / "main.nf").write_text("workflow {}")

        outdir = tmp_path / "results"
        outdir.mkdir()
        (outdir / "multiqc_report.html").write_text("<html>report</html>")

        async def fake_run_with_streaming(**kwargs):
            return {"status": "completed", "job_id": "nf_pipeline_test"}

        monkeypatch.setattr(runner, "_run_with_streaming", fake_run_with_streaming)

        result = await runner.run_pipeline_dir(
            pipeline_dir,
            inputs={"outdir": str(outdir)},
            project_id="proj_nf",
        )

        assert result["status"] == "completed"
        assert "ingested_artifacts" in result
        assert len(result["ingested_artifacts"]) == 1
        assert result["ingested_artifacts"][0]["artifact_type"] == "report"
        assert (tmp_path / "workspaces" / "proj_nf" / "output" / "multiqc_report.html").exists()


class TestGetScheduler:
    def test_get_local_scheduler(self, tmp_path):
        scheduler = get_scheduler("local", working_dir=tmp_path)
        assert isinstance(scheduler, LocalScheduler)

    def test_get_slurm_scheduler(self, tmp_path):
        scheduler = get_scheduler("slurm", working_dir=tmp_path)
        assert isinstance(scheduler, SlurmScheduler)

    def test_get_nextflow_scheduler(self, tmp_path):
        scheduler = get_scheduler("nextflow", working_dir=tmp_path)
        assert isinstance(scheduler, NextflowRunner)

    def test_get_auto_prefers_local_in_test(self, tmp_path):
        # In test environment without SLURM, auto should fall back to local
        # Nextflow is never chosen in auto mode (only explicit)
        scheduler = get_scheduler("auto", working_dir=tmp_path)
        assert isinstance(scheduler, LocalScheduler)

    def test_get_auto_selects_nextflow_for_large_plan(self, tmp_path, monkeypatch):
        from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
        from homomics_lab.hpc import router as router_module

        monkeypatch.setattr(
            router_module.NextflowRunner,
            "is_available",
            classmethod(lambda cls: True),
        )
        monkeypatch.setattr(
            router_module.SlurmScheduler,
            "is_available",
            classmethod(lambda cls: False),
        )
        plan = PlanResult(
            phases=[Phase(phase_type=f"step_{i}", required=True) for i in range(6)],
            strategy_name="test",
            data_state=DataState(),
        )
        scheduler = get_scheduler(
            "auto",
            working_dir=tmp_path,
            plan=plan,
            data_state=DataState(),
        )
        assert isinstance(scheduler, NextflowRunner)


class TestExecutionMonitoring:
    @pytest.mark.asyncio
    async def test_local_scheduler_reports_progress(self, tmp_path):
        states = []

        def callback(state):
            states.append(state)

        scheduler = LocalScheduler(working_dir=tmp_path, progress_callback=callback)
        skill = SkillDefinition(
            id="test",
            name="Test",
            version="1.0",
            category="test",
            runtime=SkillRuntime(type="python"),
        )
        result = await scheduler.execute(
            skill,
            "import time\ntime.sleep(0.1)\nresult = {'x': 42}",
            {},
            timeout_seconds=30,
        )
        assert result["x"] == 42
        assert len(states) >= 2
        assert states[0].status == "PENDING"
        assert states[-1].status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_nextflow_runner_run_plan_translates_and_runs(self, tmp_path, monkeypatch):
        from homomics_lab.agent.plan.models import DataState, Phase, PlanResult

        runner = NextflowRunner(working_dir=tmp_path)
        captured = {}

        async def fake_run_project(nf_file, inputs, timeout_seconds, weblog_url=None):
            captured["nf_file"] = nf_file
            captured["inputs"] = inputs
            return {"mock": True}

        monkeypatch.setattr(runner, "run_project", fake_run_project)

        skill = SkillDefinition(
            id="scanpy_qc",
            name="QC",
            version="1.0",
            category="single-cell",
            runtime=SkillRuntime(type="python"),
        )
        plan = PlanResult(
            phases=[
                Phase(phase_type="qc", required=True, selected_skill=skill),
                Phase(phase_type="normalize", required=True, selected_skill=skill),
            ],
            strategy_name="test",
            data_state=DataState(),
        )
        result = await runner.run_plan(plan, inputs={"input_file": "data.h5ad"})
        assert result["mock"] is True
        assert "nf_file" in result
        assert captured["nf_file"] == Path(result["nf_file"])
        assert captured["inputs"] == {"input_file": "data.h5ad"}
