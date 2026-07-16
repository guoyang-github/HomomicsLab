from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from homomics_lab.agent.plan.display_plan import DisplayStep
from homomics_lab.tasks.models import TaskNode, TaskStatus


def build_dependencies_from_phase_transitions(
    task_ids: List[str],
    phase_transitions: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """Build task dependency lists from phase transition edges.

    For each transition of type ``followed_by`` (the default) or any other
    execution-oriented edge, the ``from`` task becomes a dependency of the
    ``to`` task. ``alternative_to`` and ``parallel_to`` edges are ignored.

    When no transitions apply, a linear chain is returned (each task depends
    on the previous one in ``task_ids`` order).
    """
    incoming: Dict[str, List[str]] = {task_id: [] for task_id in task_ids}

    for transition in phase_transitions or []:
        edge_type = transition.get("type", "followed_by")
        if edge_type in ("alternative_to", "parallel_to"):
            continue
        from_id = transition.get("from")
        to_id = transition.get("to")
        if from_id and to_id and from_id in incoming and to_id in incoming:
            if from_id not in incoming[to_id]:
                incoming[to_id].append(from_id)

    # Preserve declared order; only fallback to linear if no edges resolved.
    if phase_transitions and not any(incoming.values()):
        for i, task_id in enumerate(task_ids):
            if i > 0:
                incoming[task_id].append(task_ids[i - 1])
    elif not phase_transitions:
        for i, task_id in enumerate(task_ids):
            if i > 0:
                incoming[task_id].append(task_ids[i - 1])

    return incoming


class TaskTree(BaseModel):
    tasks: List[TaskNode] = Field(default_factory=list)
    # User-facing display plan, separate from the executable tasks.
    display_steps: List[DisplayStep] = Field(default_factory=list)
    # Plan-level execution mode propagated from PlanResult.execution_mode.
    execution_mode: Optional[str] = Field(default=None)

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
