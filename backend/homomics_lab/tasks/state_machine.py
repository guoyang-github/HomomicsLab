from datetime import datetime, timezone
from typing import Set
from homomics_lab.tasks.models import TaskNode, TaskStatus


class TransitionError(ValueError):
    pass


class TaskStateMachine:
    """Manages valid transitions between task statuses."""

    VALID_TRANSITIONS: dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.PENDING: {
            TaskStatus.RUNNING,
            TaskStatus.AWAITING_HUMAN,
            TaskStatus.ABORTED,
        },
        TaskStatus.RUNNING: {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.AWAITING_HUMAN,
            TaskStatus.ABORTED,
        },
        TaskStatus.AWAITING_HUMAN: {
            TaskStatus.RUNNING,
            TaskStatus.ABORTED,
        },
        TaskStatus.FAILED: {
            TaskStatus.RUNNING,
            TaskStatus.ABORTED,
        },
        TaskStatus.COMPLETED: set(),
        TaskStatus.ABORTED: set(),
    }

    def can_transition(self, task: TaskNode, new_status: TaskStatus) -> bool:
        return new_status in self.VALID_TRANSITIONS.get(task.status, set())

    def transition(self, task: TaskNode, new_status: TaskStatus) -> None:
        if not self.can_transition(task, new_status):
            raise TransitionError(
                f"Invalid transition from {task.status.value} to {new_status.value}"
            )

        task.status = new_status

        if new_status == TaskStatus.RUNNING and task.started_at is None:
            task.started_at = datetime.now(timezone.utc)

        if new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED):
            task.completed_at = datetime.now(timezone.utc)
