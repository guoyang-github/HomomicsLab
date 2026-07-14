"""Smoke tests for the mode benchmark harness (P3-2)."""

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.mode_selection_lore import ModeSelectionLore
from homomics_lab.evaluation.mode_benchmark import (
    BenchmarkRow,
    estimate_mode_costs,
    exit_code,
    render_markdown,
    run_benchmark,
    standard_tasks,
)


def _row(task: str, expected: str, selected: str) -> BenchmarkRow:
    return BenchmarkRow(
        task=task,
        expected_mode=expected,
        selected_mode=selected,
        consistent=expected == selected,
        elapsed_ms=1.0,
        n_phases=1,
        skill_coverage=1.0,
        fixed_cost_usd=0.1,
        codeact_cost_usd=0.2,
    )


def test_synthetic_tasks_are_fully_consistent():
    """Synthetic (deterministic) tasks must always select the expected mode."""
    tasks = [t for t in standard_tasks() if t.build_plan is not None]
    assert len(tasks) >= 4
    rows = run_benchmark(tasks)
    assert all(row.consistent for row in rows)
    assert exit_code(rows) == 0


def test_render_markdown_table_shape():
    rows = [_row("t1", "auto", "auto"), _row("t2", "codeact", "auto")]
    table = render_markdown(rows)
    assert table.startswith("# fixed_pipeline vs CodeAct")
    assert "| Task | Expected | Selected |" in table
    assert "Consistency: 1/2" in table


def test_exit_code_requires_full_consistency():
    assert exit_code([_row("t1", "auto", "auto")]) == 0
    assert exit_code([_row("t1", "auto", "codeact")]) == 1
    assert exit_code([]) == 1


def test_codeact_cost_exceeds_fixed_pipeline():
    plan = PlanResult(
        phases=[Phase(phase_type="p1"), Phase(phase_type="p2")],
        strategy_name="t",
        data_state=DataState(),
    )
    fixed, codeact = estimate_mode_costs(plan)
    assert codeact > fixed
    assert fixed == 0.0  # no per-phase estimates on synthetic phases


def test_benchmark_records_mode_lore(tmp_path):
    """Benchmark writes one (intent_features -> measured_best_mode) entry per row."""
    lore = ModeSelectionLore(db_path=tmp_path / "mode_lore.db")
    tasks = [t for t in standard_tasks() if t.build_plan is not None]
    assert len(tasks) >= 4
    rows = run_benchmark(tasks, lore=lore)
    assert all(row.consistent for row in rows)
    stats = lore.get_stats()
    assert stats["keys"] > 0
    assert stats["total_weight"] >= len(tasks)
