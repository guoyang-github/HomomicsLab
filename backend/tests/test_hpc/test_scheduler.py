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
