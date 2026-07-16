"""Execution backend routing logic."""

from homomics_lab.agent.plan.models import DataState, PlanResult
from homomics_lab.config import settings
from homomics_lab.hpc.scheduler import NextflowRunner, SlurmScheduler


# Plan derivations that should never be promoted to Nextflow: they represent
# single-skill or LLM-fallback executions that are cheaper and simpler to run
# locally through the existing skill runtime.
_NON_WORKFLOW_DERIVATIONS = {"standalone-skill", "llm-fallback", "hardcoded"}


def select_execution_backend(
    plan: PlanResult,
    data_state: DataState,
    prefer_slurm: bool = True,
) -> str:
    """Select the most appropriate execution backend for a plan.

    Routing heuristics (conservative by default):
      - Nextflow is only chosen when it is enabled, the plan has at least
        ``workflow_nextflow_min_phases`` required phases (default 8), and the
        workload is large (>100 effective samples/cells) or the plan is a
        curated multi-step domain pipeline.  Small interactive analyses always
        run locally to avoid the overhead of building a Nextflow project.
      - Medium/large local workloads (>2 phases or >10 samples) prefer SLURM
        when available.
      - Everything else runs locally.

    Args:
        plan: The generated analysis plan.
        data_state: Current data state including sample/cell counts.
        prefer_slurm: Whether to prefer SLURM over local for medium workloads.

    Returns:
        One of "local", "slurm", or "nextflow".
    """
    nextflow_enabled = getattr(settings, "workflow_nextflow_enabled", True)

    n_phases = len([p for p in plan.phases if p.required])
    n_samples = data_state.n_samples or 1
    n_cells = data_state.n_cells or 0
    # Use cells as a proxy for samples when only cell count is available.
    effective_samples = max(n_samples, n_cells)

    derivation = getattr(plan, "derivation", None) or ""
    is_large_workflow = (
        n_phases >= getattr(settings, "workflow_nextflow_min_phases", 8)
        and derivation not in _NON_WORKFLOW_DERIVATIONS
    )

    if nextflow_enabled and is_large_workflow and effective_samples > 100:
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
