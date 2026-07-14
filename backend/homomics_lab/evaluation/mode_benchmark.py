"""A/B benchmark: fixed_pipeline vs CodeAct plan-level execution modes.

Quantifies the planning-layer trade-off between the two modes on a standard
task set — no skills are actually executed.  For each task the benchmark
measures:

  - mode selection correctness: does ``ModeSelector`` (as wired into
    ``PlanEngine``) pick the expected mode for the task?
  - plan generation latency (ms)
  - estimated cost of running the plan under each mode (USD)
  - consistency: selected mode == expected mode

Everything is deterministic and offline: skills live in an in-memory
``SkillRegistry`` and the only LLM involved is ``FakeLLMClient``.
Coverage-sensitive tasks build their ``PlanResult`` synthetically instead of
running the engine: although the engine's fallback matcher is now gated by a
similarity floor (``PlanEngine.fallback_min_similarity``), synthetic plans
keep coverage exactly deterministic regardless of index contents.

Run directly::

    python -m homomics_lab.evaluation.mode_benchmark

Exit code is 0 when every task's selected mode matches the expected mode.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.llm_fallback import LLMFallbackPlanner
from homomics_lab.agent.plan.mode_selector import ModeSelector
from homomics_lab.agent.plan.mode_selection_lore import ModeSelectionLore
from homomics_lab.agent.plan.models import DataState, PlannedGap, PlanResult
from homomics_lab.agent.plan.strategies import AnalysisStrategy, Phase, StrategyLibrary
from homomics_lab.agent.retrieval import RetrievalContext, SkillRetriever
from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.skills.models import (
    SkillDefinition,
    SkillInputSchema,
    SkillOutputSchema,
)
from homomics_lab.skills.registry import SkillRegistry

# ── Cost model ──────────────────────────────────────────────────────────
# fixed_pipeline runs curated skills only: cost = sum of per-phase estimates
# (no LLM tokens).  CodeAct additionally pays for LLM code generation; the
# token estimate below uses the same placeholder rates as plan/estimator.py
# (~$0.50/$1.50 per 1M input/output tokens).
CODEACT_INPUT_TOKENS_PER_PHASE = 2000
CODEACT_OUTPUT_TOKENS_PER_PHASE = 1000
LLM_INPUT_TOKEN_COST = 5e-7  # USD per token
LLM_OUTPUT_TOKEN_COST = 1.5e-6  # USD per token


def estimate_mode_costs(plan: PlanResult) -> Tuple[float, float]:
    """Return (fixed_pipeline_cost_usd, codeact_cost_usd) for a plan."""
    fixed = plan.total_estimated_cost_usd or 0.0
    n_phases = max(len(plan.phases), 1)
    llm_cost = n_phases * (
        CODEACT_INPUT_TOKENS_PER_PHASE * LLM_INPUT_TOKEN_COST
        + CODEACT_OUTPUT_TOKENS_PER_PHASE * LLM_OUTPUT_TOKEN_COST
    )
    return fixed, fixed + llm_cost


# ── Task set ────────────────────────────────────────────────────────────


@dataclass
class BenchmarkTask:
    """One standard task plus its expected mode.

    Two kinds of tasks are supported:

    - engine tasks (``build_engine``): run the full ``PlanEngine`` pipeline
      end-to-end and read ``plan.execution_mode`` as filled by the wired
      ``ModeSelector``.
    - plan tasks (``build_plan``): build a ``PlanResult`` synthetically and
      run ``ModeSelector.select`` directly. Used for coverage-sensitive
      scenarios so coverage stays exactly deterministic regardless of the
      engine's threshold-gated fallback matcher.
    """

    name: str
    description: str
    expected_mode: str  # "fixed_pipeline" | "codeact" | "auto"
    build_engine: Optional[Callable[[], Tuple[PlanEngine, UserIntent, str]]] = None
    build_plan: Optional[Callable[[], PlanResult]] = None


@dataclass
class BenchmarkRow:
    task: str
    expected_mode: str
    selected_mode: str
    consistent: bool
    elapsed_ms: float
    n_phases: int
    skill_coverage: float
    fixed_cost_usd: float
    codeact_cost_usd: float


class _EmptyRetriever(SkillRetriever):
    """SkillRetriever stub: no plan-wide retrieval, no CBKB side effects.

    Per-phase skill selection then depends only on the strategy skeleton's
    ``candidate_skills``, which keeps task coverage deterministic.
    """

    def __init__(self) -> None:
        self.literature_retriever = None

    async def retrieve(self, **kwargs) -> RetrievalContext:  # type: ignore[override]
        return RetrievalContext(
            query=kwargs.get("query", ""),
            intent_type=kwargs.get("intent_type", ""),
            skills=[],
            tools=[],
            data_sources=[],
            literature=[],
            sops=[],
            anomalies=[],
            parameter_lore=[],
        )


def _make_skill(
    skill_id: str,
    description: str,
    input_required: Optional[List[str]] = None,
    output_props: Optional[List[str]] = None,
) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        version="1.0",
        category="single_cell",
        description=description,
        input_schema=SkillInputSchema(required=input_required or []),
        output_schema=SkillOutputSchema(
            properties={p: {"type": "string"} for p in (output_props or [])}
        ),
        domains=["single_cell"],
    )


def _build_engine(
    registry: SkillRegistry,
    strategy: AnalysisStrategy,
    llm_fallback: Optional[LLMFallbackPlanner] = None,
) -> PlanEngine:
    library = StrategyLibrary(skill_registry=registry)
    library.register(strategy)
    return PlanEngine(
        skill_registry=registry,
        strategy_library=library,
        skill_retriever=_EmptyRetriever(),
        llm_fallback=llm_fallback,
    )


def _sc_strategy(name: str, skeleton: List[Phase]) -> AnalysisStrategy:
    return AnalysisStrategy(
        name=name,
        description=f"Benchmark strategy {name}",
        applicable_intents=["single_cell_analysis"],
        skeleton=skeleton,
    )


def _intent(analysis_type: str = "single_cell_analysis") -> UserIntent:
    return UserIntent(analysis_type=analysis_type, complexity="complex", confidence=0.9)


# Descriptions must not contain the tokens "analysis"/"step" (they appear in
# every auto-generated phase description) so that, before the fallback
# similarity floor existed, uncovered phases could not match skills via the
# fallback search.  Kept as a guard for the thresholded matcher as well.
_FULL_SKILLS = [
    _make_skill("scanpy_qc", "Quality control of droplet count matrices"),
    _make_skill("scanpy_normalize", "Library-size normalization and log transform"),
    _make_skill("scanpy_pca", "Principal component embedding of expression"),
    _make_skill("scanpy_cluster", "Leiden community detection on neighbour graph"),
]


def _build_full_coverage() -> Tuple[PlanEngine, UserIntent, str]:
    registry = SkillRegistry()
    for skill in _FULL_SKILLS:
        registry.register(skill)
    strategy = _sc_strategy(
        "bench_full",
        [
            Phase(phase_type="qc", candidate_skills=["scanpy_qc"]),
            Phase(phase_type="normalization", candidate_skills=["scanpy_normalize"]),
            Phase(phase_type="dim_reduction", candidate_skills=["scanpy_pca"]),
            Phase(phase_type="clustering", candidate_skills=["scanpy_cluster"]),
        ],
    )
    return _build_engine(registry, strategy), _intent(), "bench_full"


def _synthetic_plan(
    n_phases: int,
    n_covered: int,
    gaps: Optional[List[PlannedGap]] = None,
    risk_level: str = "low",
) -> PlanResult:
    """Build a PlanResult with a deterministic skill coverage ratio."""
    skill = _make_skill("curated_step", "Curated pipeline step")
    phases = [
        Phase(
            phase_type=f"phase_{i}",
            selected_skill=skill if i < n_covered else None,
        )
        for i in range(n_phases)
    ]
    return PlanResult(
        phases=phases,
        strategy_name="synthetic",
        data_state=DataState(),
        gaps=gaps or [],
        risk_level=risk_level,
    )


def _build_partial_coverage() -> PlanResult:
    return _synthetic_plan(n_phases=4, n_covered=2)


def _build_low_coverage() -> PlanResult:
    return _synthetic_plan(n_phases=4, n_covered=1)


def _build_schema_gaps() -> PlanResult:
    gaps = [
        PlannedGap(
            from_phase="phase_0",
            to_phase="phase_1",
            from_skill="curated_step",
            to_skill="curated_step",
            gap_type="field_missing",
        ),
        PlannedGap(
            from_phase="phase_1",
            to_phase="phase_2",
            from_skill="curated_step",
            to_skill="curated_step",
            gap_type="format_conversion",
        ),
    ]
    return _synthetic_plan(n_phases=3, n_covered=3, gaps=gaps)


def _build_high_risk() -> PlanResult:
    return _synthetic_plan(n_phases=3, n_covered=3, risk_level="high")


def _build_single_step() -> Tuple[PlanEngine, UserIntent, str]:
    registry = SkillRegistry()
    registry.register(
        _make_skill("convert_h5ad_to_rds", "Format conversion between count stores")
    )
    strategy = _sc_strategy(
        "bench_single",
        [Phase(phase_type="format_convert", candidate_skills=["convert_h5ad_to_rds"])],
    )
    return _build_engine(registry, strategy), _intent(), "bench_single"


def _build_open_ended() -> Tuple[PlanEngine, UserIntent, str]:
    """Unknown intent -> generic strategy -> LLM fallback via FakeLLMClient."""
    registry = SkillRegistry()
    registry.register(
        _make_skill("core_code_act", "General code generation assistant")
    )
    fake_response = json.dumps(
        {
            "steps": [
                {
                    "skill_id": "core_code_act",
                    "phase": "analysis",
                    "reason": "No curated skill covers this novel assay",
                    "parameters": {},
                }
            ],
            "summary": "CodeAct fallback plan",
        }
    )
    llm_fallback = LLMFallbackPlanner(
        registry,
        llm_client=FakeLLMClient(response=fake_response),
    )
    strategy = _sc_strategy(
        "generic",
        [Phase(phase_type="data_loading"), Phase(phase_type="analysis")],
    )
    engine = _build_engine(registry, strategy, llm_fallback=llm_fallback)
    return engine, _intent("novel_unmodeled_assay"), "generic"


def standard_tasks() -> List[BenchmarkTask]:
    """The standard A/B task set."""
    return [
        BenchmarkTask(
            name="full_coverage_sc_pipeline",
            description="Standard scRNA-seq workflow, all phases have curated skills",
            expected_mode="fixed_pipeline",
            build_engine=_build_full_coverage,
        ),
        BenchmarkTask(
            name="partial_coverage_pipeline",
            description="Half of the phases lack curated skills",
            expected_mode="auto",
            build_plan=_build_partial_coverage,
        ),
        BenchmarkTask(
            name="low_coverage_pipeline",
            description="Only one phase has a curated skill",
            expected_mode="codeact",
            build_plan=_build_low_coverage,
        ),
        BenchmarkTask(
            name="schema_gap_pipeline",
            description="Fully covered but chained skills have schema gaps",
            expected_mode="codeact",
            build_plan=_build_schema_gaps,
        ),
        BenchmarkTask(
            name="high_risk_pipeline",
            description="Fully covered but the plan carries high risk",
            expected_mode="auto",
            build_plan=_build_high_risk,
        ),
        BenchmarkTask(
            name="single_step_file_convert",
            description="Atomic file-format conversion with one curated skill",
            expected_mode="fixed_pipeline",
            build_engine=_build_single_step,
        ),
        BenchmarkTask(
            name="open_ended_no_domain",
            description="Novel assay, no domain strategy — LLM fallback plan",
            expected_mode="codeact",
            build_engine=_build_open_ended,
        ),
    ]


# ── Feedback helpers ────────────────────────────────────────────────────


def _measured_best_mode(row: BenchmarkRow) -> Tuple[str, float]:
    """Derive the measured-best mode and a win margin for a benchmark row.

    The benchmark itself does not execute plans, so the "measured best" is
    approximated from the task label and the estimated mode costs:

      - ``expected_mode`` is treated as the best mode for the task.
      - ``win_margin`` is the absolute cost difference between the two
        concrete modes, used to weight the observation in the lore.
    """
    margin = abs(row.codeact_cost_usd - row.fixed_cost_usd)
    return row.expected_mode, margin


def _record_row_feedback(
    lore: ModeSelectionLore,
    plan: PlanResult,
    row: BenchmarkRow,
) -> None:
    """Write one benchmark observation into the mode-selection lore."""
    features = ModeSelector.extract_intent_features(plan)
    measured_mode, margin = _measured_best_mode(row)
    # Weight the observation by a baseline 1.0 plus the cost win margin so
    # larger savings contribute more to the learned prior.
    lore.record(features, measured_mode, outcome_score=1.0 + margin)


# ── Runner ──────────────────────────────────────────────────────────────


async def _run_task(
    task: BenchmarkTask,
    selector: Optional[ModeSelector] = None,
    lore: Optional[ModeSelectionLore] = None,
) -> BenchmarkRow:
    if task.build_plan is not None:
        # Synthetic plan: measure the selector directly, the same way
        # PlanEngine fills the field for engine-built plans.
        plan = task.build_plan()
        start = time.perf_counter()
        plan.execution_mode = (selector or ModeSelector()).select(plan)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
    elif task.build_engine is not None:
        engine, intent, strategy_name = task.build_engine()
        start = time.perf_counter()
        plan = await engine.plan(intent, DataState(), strategy_name=strategy_name)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
    else:
        raise ValueError(f"BenchmarkTask '{task.name}' has no builder")

    selected = plan.execution_mode
    fixed_cost, codeact_cost = estimate_mode_costs(plan)
    coverage = (
        sum(1 for p in plan.phases if p.selected_skill is not None) / len(plan.phases)
        if plan.phases
        else 0.0
    )
    row = BenchmarkRow(
        task=task.name,
        expected_mode=task.expected_mode,
        selected_mode=selected,
        consistent=selected == task.expected_mode,
        elapsed_ms=elapsed_ms,
        n_phases=len(plan.phases),
        skill_coverage=coverage,
        fixed_cost_usd=fixed_cost,
        codeact_cost_usd=codeact_cost,
    )
    if lore is not None:
        _record_row_feedback(lore, plan, row)
    return row


def run_benchmark(
    tasks: Optional[List[BenchmarkTask]] = None,
    selector: Optional[ModeSelector] = None,
    lore: Optional[ModeSelectionLore] = None,
) -> List[BenchmarkRow]:
    """Run every task and return the per-task rows.

    When ``lore`` is provided, each row is also recorded as a
    ``(intent_features -> measured_best_mode)`` observation so the
    ``ModeSelector`` prior evolves with benchmark runs.
    """
    tasks = tasks if tasks is not None else standard_tasks()

    async def _run_all() -> List[BenchmarkRow]:
        return [await _run_task(task, selector=selector, lore=lore) for task in tasks]

    return asyncio.run(_run_all())


def render_markdown(rows: List[BenchmarkRow]) -> str:
    """Render the benchmark rows as a markdown comparison table."""
    lines = [
        "# fixed_pipeline vs CodeAct — plan-level mode benchmark",
        "",
        "| Task | Expected | Selected | Consistent | Time (ms) | Phases | Coverage | fixed_pipeline ($) | codeact ($) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        mark = "✓" if row.consistent else "✗"
        lines.append(
            f"| {row.task} | {row.expected_mode} | {row.selected_mode} | {mark} "
            f"| {row.elapsed_ms:.1f} | {row.n_phases} | {row.skill_coverage:.2f} "
            f"| {row.fixed_cost_usd:.6f} | {row.codeact_cost_usd:.6f} |"
        )
    consistent = sum(1 for row in rows if row.consistent)
    total_ms = sum(row.elapsed_ms for row in rows)
    lines.extend(
        [
            "",
            f"Consistency: {consistent}/{len(rows)} "
            f"({consistent / len(rows) * 100:.0f}%) — total planning time {total_ms:.1f} ms",
        ]
    )
    return "\n".join(lines)


def exit_code(rows: List[BenchmarkRow]) -> int:
    """0 when every task selected its expected mode."""
    return 0 if rows and all(row.consistent for row in rows) else 1


def main() -> int:
    selector = ModeSelector()
    lore = ModeSelectionLore()
    rows = run_benchmark(selector=selector, lore=lore)
    print(render_markdown(rows))
    stats = lore.get_stats()
    print(
        f"\nMode-selection lore updated: {stats['keys']} feature keys, "
        f"{stats['total_weight']:.2f} total observation weight."
    )
    return exit_code(rows)


if __name__ == "__main__":
    sys.exit(main())
