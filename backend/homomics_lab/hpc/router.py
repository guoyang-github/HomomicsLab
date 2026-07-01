"""Execution backend routing logic."""

from homomics_lab.agent.plan.models import DataState, PlanResult
from homomics_lab.config import settings
from homomics_lab.hpc.scheduler import NextflowRunner, SlurmScheduler


def select_execution_backend(
    plan: PlanResult,
    data_state: DataState,
    prefer_slurm: bool = True,
) -> str:
    """Select the most appropriate execution backend for a plan.

    Routing heuristics:
      - Large/complex plans (>5 phases or >100 samples) prefer Nextflow when available.
      - Medium workloads (>2 phases or >10 samples) prefer SLURM when available.
      - Everything else runs locally.

    Args:
        plan: The generated analysis plan.
        data_state: Current data state including sample/cell counts.
        prefer_slurm: Whether to prefer SLURM over local for medium workloads.

    Returns:
        One of "local", "slurm", or "nextflow".
    """
    n_phases = len([p for p in plan.phases if p.required])
    n_samples = data_state.n_samples or 1
    n_cells = data_state.n_cells or 0
    # Use cells as a proxy for samples when only cell count is available.
    effective_samples = max(n_samples, n_cells)

    min_phases = getattr(settings, "workflow_nextflow_min_phases", 5)
    if n_phases >= min_phases or effective_samples > 100:
        if NextflowRunner.is_available():
            return "nextflow"
        if SlurmScheduler.is_available() and prefer_slurm:
            return "slurm"
        return "local"

    if SlurmScheduler.is_available() and prefer_slurm and (
        effective_samples > 10 or n_phases > 2
    ):
        return "slurm"

    return "local"
