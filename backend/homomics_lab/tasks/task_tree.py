from typing import List, Optional
from pydantic import BaseModel, Field
from homomics_lab.tasks.models import TaskNode, TaskStatus


class TaskTree(BaseModel):
    tasks: List[TaskNode] = Field(default_factory=list)

    def __init__(self, tasks: Optional[List[TaskNode]] = None, **data):
        if tasks is not None and "tasks" not in data:
            data["tasks"] = tasks
        super().__init__(**data)

    def get_task(self, task_id: str) -> TaskNode:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Task {task_id} not found")

    def get_ready_tasks(self) -> List[TaskNode]:
        """Return tasks whose dependencies are all completed and status is pending."""
        completed = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [t for t in self.tasks if t.status == TaskStatus.PENDING and all(dep in completed for dep in t.dependencies)]

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
