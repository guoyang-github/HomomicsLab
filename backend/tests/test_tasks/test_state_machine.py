import pytest
from homics_lab.tasks.models import TaskNode, TaskStatus
from homics_lab.tasks.state_machine import TaskStateMachine, TransitionError


@pytest.fixture
def sm():
    return TaskStateMachine()


def test_pending_to_running(sm):
    task = TaskNode(id="t1", name="test", description="test")
    sm.transition(task, TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING

def test_running_to_completed(sm):
    task = TaskNode(id="t1", name="test", description="test")
    task.status = TaskStatus.RUNNING
    sm.transition(task, TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED

def test_invalid_transition_raises(sm):
    task = TaskNode(id="t1", name="test", description="test")
    task.status = TaskStatus.COMPLETED
    with pytest.raises(TransitionError):
        sm.transition(task, TaskStatus.RUNNING)

def test_awaiting_human_transition(sm):
    task = TaskNode(id="t1", name="test", description="test")
    task.status = TaskStatus.RUNNING
    sm.transition(task, TaskStatus.AWAITING_HUMAN)
    assert task.status == TaskStatus.AWAITING_HUMAN

    sm.transition(task, TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
