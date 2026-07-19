"""Tests for execution backend routing."""

import pytest

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.hpc import router as router_module
from homomics_lab.hpc.router import select_execution_backend


@pytest.fixture
def patch_backends(monkeypatch):
    """Patch backend availability for deterministic routing tests."""
    def _patch(slurm: bool = False, nextflow: bool = False):
        monkeypatch.setattr(
            router_module.SlurmScheduler,
            "is_available",
            classmethod(lambda cls: slurm),
        )
        monkeypatch.setattr(
            router_module.NextflowRunner,
            "is_available",
            classmethod(lambda cls: nextflow),
        )
    return _patch


class TestSelectExecutionBackend:
    def test_small_plan_runs_local(self, patch_backends):
        patch_backends(slurm=False, nextflow=False)
        plan = PlanResult(
            phases=[Phase(phase_type="qc", required=True)],
            strategy_name="test",
            data_state=DataState(),
        )
        assert select_execution_backend(plan, DataState()) == "local"

    def test_medium_plan_prefers_slurm(self, patch_backends):
        patch_backends(slurm=True, nextflow=False)
        plan = PlanResult(
            phases=[
                Phase(phase_type="qc", required=True),
                Phase(phase_type="normalize", required=True),
                Phase(phase_type="cluster", required=True),
            ],
            strategy_name="test",
            data_state=DataState(),
        )
        assert select_execution_backend(plan, DataState()) == "slurm"

    def test_large_plan_prefers_nextflow(self, patch_backends):
        patch_backends(slurm=False, nextflow=True)
        plan = PlanResult(
            phases=[Phase(phase_type=f"step_{i}", required=True) for i in range(10)],
            strategy_name="test",
            data_state=DataState(),
        )
        data_state = DataState(n_samples=200)
        assert select_execution_backend(plan, data_state) == "nextflow"

    def test_plan_below_min_phases_runs_local_even_with_nextflow(self, patch_backends):
        """Small plans must not pay the Nextflow overhead."""
        patch_backends(slurm=False, nextflow=True)
        plan = PlanResult(
            phases=[Phase(phase_type=f"step_{i}", required=True) for i in range(6)],
            strategy_name="test",
            data_state=DataState(),
        )
        assert select_execution_backend(plan, DataState()) == "local"

    def test_many_samples_routes_to_nextflow(self, patch_backends):
        patch_backends(slurm=False, nextflow=True)
        plan = PlanResult(
            phases=[Phase(phase_type="qc", required=True)],
            strategy_name="test",
            data_state=DataState(),
        )
        # A single phase is below the Nextflow phase threshold, so it stays local.
        assert select_execution_backend(plan, DataState(n_samples=200)) == "local"

    def test_cells_proxy_for_samples(self, patch_backends):
        patch_backends(slurm=False, nextflow=True)
        plan = PlanResult(
            phases=[Phase(phase_type="qc", required=True)],
            strategy_name="test",
            data_state=DataState(),
        )
        # A single phase is below the Nextflow phase threshold, so it stays local.
        assert select_execution_backend(plan, DataState(n_cells=5000)) == "local"

    def test_large_dataset_with_enough_phases_routes_to_nextflow(self, patch_backends):
        patch_backends(slurm=False, nextflow=True)
        plan = PlanResult(
            phases=[Phase(phase_type=f"step_{i}", required=True) for i in range(10)],
            strategy_name="test",
            data_state=DataState(),
        )
        assert select_execution_backend(plan, DataState(n_cells=5000)) == "nextflow"

    def test_standalone_skill_never_routes_to_nextflow(self, patch_backends):
        """Single-skill tasks (e.g. CellTypist) should never trigger Nextflow."""
        patch_backends(slurm=False, nextflow=True)
        plan = PlanResult(
            phases=[Phase(phase_type="annotation", required=True)],
            strategy_name="test",
            derivation="standalone-skill",
            data_state=DataState(),
        )
        assert select_execution_backend(plan, DataState(n_cells=500000)) == "local"

    def test_llm_fallback_never_routes_to_nextflow(self, patch_backends):
        patch_backends(slurm=False, nextflow=True)
        plan = PlanResult(
            phases=[Phase(phase_type=f"step_{i}", required=True) for i in range(10)],
            strategy_name="test",
            derivation="llm-fallback",
            data_state=DataState(),
        )
        assert select_execution_backend(plan, DataState(n_samples=200)) == "local"

    def test_nextflow_disabled_runs_local(self, patch_backends, monkeypatch):
        patch_backends(slurm=False, nextflow=True)
        monkeypatch.setattr(
            router_module,
            "WORKFLOW_NEXTFLOW_ENABLED",
            False,
        )
        plan = PlanResult(
            phases=[Phase(phase_type=f"step_{i}", required=True) for i in range(10)],
            strategy_name="test",
            data_state=DataState(),
        )
        assert select_execution_backend(plan, DataState(n_samples=200)) == "local"
