"""Tests for SkillRuntimeExecutor backend routing."""

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.hpc import router as router_module
from homomics_lab.skills.runtime import SkillRuntimeExecutor


class TestSkillRuntimeExecutorBackend:
    def test_select_backend_routes_large_plan_to_nextflow(self, monkeypatch):
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
        executor = SkillRuntimeExecutor(executor_type="local")
        plan = PlanResult(
            phases=[Phase(phase_type=f"step_{i}", required=True) for i in range(6)],
            strategy_name="test",
            data_state=DataState(),
        )
        backend = executor.select_backend_for(plan, DataState())
        assert backend == "nextflow"
        assert executor._executor_type == "nextflow"
        assert executor._scheduler is None

    def test_select_backend_routes_small_plan_to_local(self, monkeypatch):
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
        executor = SkillRuntimeExecutor(executor_type="local")
        plan = PlanResult(
            phases=[Phase(phase_type="qc", required=True)],
            strategy_name="test",
            data_state=DataState(),
        )
        backend = executor.select_backend_for(plan, DataState())
        assert backend == "local"
