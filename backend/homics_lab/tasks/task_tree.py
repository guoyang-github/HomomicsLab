from typing import List
from homics_lab.tasks.models import TaskNode


class TaskTree:
    def __init__(self, tasks: List[TaskNode] = None):
        self.tasks = tasks or []

    def get_task(self, task_id: str) -> TaskNode:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Task {task_id} not found")

    def topological_sort(self) -> List[TaskNode]:
        """Return tasks in dependency order."""
        completed = set()
        result = []

        def can_schedule(task: TaskNode) -> bool:
            return all(dep in completed for dep in task.dependencies)

        pending = list(self.tasks)
        while pending:
            progress = False
            for task in pending[:]:
                if can_schedule(task):
                    result.append(task)
                    completed.add(task.id)
                    pending.remove(task)
                    progress = True

            if not progress and pending:
                raise ValueError("Cyclic dependency detected in task tree")

        return result
