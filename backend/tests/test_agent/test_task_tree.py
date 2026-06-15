"""Tests for TaskTree serialization."""

import pytest
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.tasks.models import TaskNode, TaskStatus


def test_task_tree_round_trip():
    """Build a TaskTree with two TaskNodes, one dependent on the other."""
    task_a = TaskNode(id="task-a", name="First task", description="First task", status=TaskStatus.COMPLETED, dependencies=[])
    task_b = TaskNode(id="task-b", name="Second task", description="Second task", status=TaskStatus.PENDING, dependencies=["task-a"])
    tree = TaskTree(tasks=[task_a, task_b])

    dumped = tree.model_dump()
    restored = TaskTree.model_validate(dumped)

    assert len(restored.tasks) == 2
    assert restored.tasks[0].id == "task-a"
    assert restored.tasks[1].id == "task-b"
    assert restored.tasks[1].dependencies == ["task-a"]


def test_task_tree_empty_round_trip():
    """Empty TaskTree round-trip."""
    tree = TaskTree()
    dumped = tree.model_dump()
    restored = TaskTree.model_validate(dumped)
    assert restored.tasks == []
