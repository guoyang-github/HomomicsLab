"""Tests for IntentRouter helpers."""

from types import SimpleNamespace

from homomics_lab.agent.turn_intent_router import IntentRouter


def test_build_initial_progress_uses_display_steps():
    tree = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                id="t1",
                name="annotation",
                description="Run CellTypist",
                phase="annotation",
            )
        ],
        display_steps=[
            SimpleNamespace(
                id="ds_1",
                description="Annotate cells with CellTypist",
                phase_type="annotation",
                analysis_type="annotation",
            ),
            SimpleNamespace(
                id="ds_2",
                description="Compare predicted labels with existing annotations",
                phase_type="annotation",
                analysis_type="label_comparison",
            ),
        ],
    )
    progress, tasks = IntentRouter.build_initial_progress(tree)
    assert progress["total"] == 2
    assert len(tasks) == 2
    assert tasks[0]["analysis_type"] == "annotation"
    assert tasks[1]["analysis_type"] == "label_comparison"


def test_build_initial_progress_falls_back_to_tasks():
    tree = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                id="t1",
                name="qc",
                description="Quality control",
                phase="qc",
            )
        ],
        display_steps=[],
    )
    progress, tasks = IntentRouter.build_initial_progress(tree)
    assert progress["total"] == 1
    assert len(tasks) == 1
    assert tasks[0]["name"] == "qc"
