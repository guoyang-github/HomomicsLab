"""Tests for SkillDAG observation recording in TurnRunner execution feedback."""

from unittest.mock import MagicMock, patch

import pytest

from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.skills.skill_dag import EdgeType
from homomics_lab.tasks.models import TaskNode, TaskStatus
from homomics_lab.tasks.task_tree import TaskTree


def _make_tree(*specs):
    """specs: list of (task_id, skill_id, status)."""
    tree = TaskTree(
        tasks=[
            TaskNode(
                id=tid,
                name=tid,
                description="",
                skills_required=[skill] if skill else [],
            )
            for tid, skill, _ in specs
        ]
    )
    for task, (_, _, status) in zip(tree.tasks, specs):
        task.status = status
    return tree


@pytest.mark.asyncio
async def test_records_followed_by_for_adjacent_skills():
    skill_dag = MagicMock()
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", "scanpy_norm", TaskStatus.COMPLETED),
    )

    await runner._record_execution_feedback(tree, {}, "proj_1")

    skill_dag.record_observation.assert_called_once()
    args = skill_dag.record_observation.call_args.args
    assert args[0] == "scanpy_qc"
    assert args[1] == "scanpy_norm"
    assert args[2] == EdgeType.FOLLOWED_BY
    assert args[3] is True


@pytest.mark.asyncio
async def test_failed_successor_marks_observation_unsuccessful():
    skill_dag = MagicMock()
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", "scanpy_norm", TaskStatus.FAILED),
    )

    await runner._record_execution_feedback(tree, {}, "proj_1")

    skill_dag.record_observation.assert_called_once()
    assert skill_dag.record_observation.call_args.args[3] is False


@pytest.mark.asyncio
async def test_skips_tasks_without_skills_and_duplicate_transitions():
    skill_dag = MagicMock()
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", None, TaskStatus.COMPLETED),  # no skill bound
        ("t3", "scanpy_qc", TaskStatus.COMPLETED),  # same skill as t1
        ("t4", "scanpy_cluster", TaskStatus.COMPLETED),
    )

    await runner._record_execution_feedback(tree, {}, "proj_1")

    skill_dag.record_observation.assert_called_once()
    args = skill_dag.record_observation.call_args.args
    assert args[0] == "scanpy_qc"
    assert args[1] == "scanpy_cluster"


@pytest.mark.asyncio
async def test_single_skill_task_records_no_observation():
    skill_dag = MagicMock()
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(("t1", "scanpy_qc", TaskStatus.COMPLETED))

    await runner._record_execution_feedback(tree, {}, "proj_1")

    skill_dag.record_observation.assert_not_called()


@pytest.mark.asyncio
async def test_dag_errors_never_break_feedback():
    skill_dag = MagicMock()
    skill_dag.record_observation.side_effect = RuntimeError("dag broken")
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", "scanpy_norm", TaskStatus.COMPLETED),
    )

    # Must not raise — feedback is best-effort.
    await runner._record_execution_feedback(tree, {}, "proj_1")


@pytest.mark.asyncio
async def test_no_skill_dag_is_noop():
    runner = TurnRunner()
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", "scanpy_norm", TaskStatus.COMPLETED),
    )

    await runner._record_execution_feedback(tree, {}, "proj_1")


@pytest.mark.asyncio
async def test_promotes_observed_seed_edges_for_successful_pairs():
    skill_dag = MagicMock()
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", "scanpy_norm", TaskStatus.COMPLETED),
    )

    with patch(
        "homomics_lab.agent.turn_feedback_recorder.record_observed_seed_edges"
    ) as mock:
        await runner._record_execution_feedback(tree, {}, "proj_1")

    mock.assert_called_once()
    args = mock.call_args.args
    assert args[0] is skill_dag
    assert args[1] == [("scanpy_qc", "scanpy_norm")]


@pytest.mark.asyncio
async def test_failed_pairs_are_not_submitted_as_observed_seeds():
    skill_dag = MagicMock()
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", "scanpy_norm", TaskStatus.FAILED),
    )

    with patch(
        "homomics_lab.agent.turn_feedback_recorder.record_observed_seed_edges"
    ) as mock:
        await runner._record_execution_feedback(tree, {}, "proj_1")

    mock.assert_not_called()


@pytest.mark.asyncio
async def test_observed_seed_errors_never_break_feedback():
    skill_dag = MagicMock()
    runner = TurnRunner(skill_dag=skill_dag)
    tree = _make_tree(
        ("t1", "scanpy_qc", TaskStatus.COMPLETED),
        ("t2", "scanpy_norm", TaskStatus.COMPLETED),
    )

    with patch(
        "homomics_lab.agent.turn_feedback_recorder.record_observed_seed_edges",
        side_effect=RuntimeError("observed seed broken"),
    ):
        await runner._record_execution_feedback(tree, {}, "proj_1")
