import pytest
from homics_lab.tasks.task_tree import TaskTree
from homics_lab.tasks.models import TaskNode, TaskStatus


def test_topological_sort_simple():
    tree = TaskTree([
        TaskNode(id="t1", name="a", description="first", status=TaskStatus.PENDING, dependencies=[], skills_required=[], estimated_duration_minutes=10, parameters={}),
        TaskNode(id="t2", name="b", description="second", status=TaskStatus.PENDING, dependencies=["t1"], skills_required=[], estimated_duration_minutes=10, parameters={}),
    ])
    sorted_tasks = tree.topological_sort()
    assert sorted_tasks[0].id == "t1"
    assert sorted_tasks[1].id == "t2"


def test_topological_sort_detects_cycle():
    tree = TaskTree([
        TaskNode(id="t1", name="a", description="first", status=TaskStatus.PENDING, dependencies=["t2"], skills_required=[], estimated_duration_minutes=10, parameters={}),
        TaskNode(id="t2", name="b", description="second", status=TaskStatus.PENDING, dependencies=["t1"], skills_required=[], estimated_duration_minutes=10, parameters={}),
    ])
    with pytest.raises(ValueError):
        tree.topological_sort()


def test_ready_tasks():
    tree = TaskTree([
        TaskNode(id="t1", name="a", description="first", status=TaskStatus.PENDING, dependencies=[], skills_required=[], estimated_duration_minutes=10, parameters={}),
        TaskNode(id="t2", name="b", description="second", status=TaskStatus.PENDING, dependencies=["t1"], skills_required=[], estimated_duration_minutes=10, parameters={}),
    ])
    ready = tree.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == "t1"
