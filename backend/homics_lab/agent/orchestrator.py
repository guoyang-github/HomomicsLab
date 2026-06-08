from typing import Any, Dict
from homics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homics_lab.tasks.task_tree import TaskTree
from homics_lab.models.common import TaskStatus
from homics_lab.tasks.models import TaskNode
from homics_lab.tasks.state_machine import TaskStateMachine


class Orchestrator:
    """Central task scheduler and executor."""

    def __init__(self, registry: AgentRegistry = None):
        self.registry = registry or get_default_registry()
        self.state_machine = TaskStateMachine()

    async def run_tree(self, tree: TaskTree, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        results = {}
        completed = set()

        for task in tree.topological_sort():
            # Check dependencies are satisfied
            if not all(dep in completed for dep in task.dependencies):
                raise ValueError(f"Dependencies not satisfied for task {task.id}")

            # Transition to running
            self.state_machine.transition(task, TaskStatus.RUNNING)

            try:
                # Find agent for this task
                agent = self._resolve_agent(task)

                if agent is None:
                    raise RuntimeError(f"No agent found for task {task.name}")

                # Execute task
                result = await agent.run(task, context)
                results[task.id] = result
                task.result = result

                # Transition to completed
                self.state_machine.transition(task, TaskStatus.COMPLETED)
                completed.add(task.id)

            except Exception as e:
                task.error_message = str(e)
                task.attempt_count += 1

                if task.attempt_count < task.retry_policy.max_attempts:
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    # In a real system, retry with backoff
                    raise  # For MVP, just raise
                else:
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    raise

        return results

    def _resolve_agent(self, task: TaskNode):
        """Find the best agent for a task."""
        # First try by explicit assignment
        if task.agent_assignment:
            agent = self.registry.get_agent(task.agent_assignment)
            if agent:
                return agent

        # Then try by required skills
        for skill in task.skills_required:
            agent = self.registry.find_agent_for_task(skill)
            if agent:
                return agent

        return None

    def get_progress(self, tree: TaskTree) -> Dict[str, int]:
        total = len(tree.tasks)
        by_status = {
            "total": total,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
        }

        for task in tree.tasks:
            if task.status == TaskStatus.PENDING:
                by_status["pending"] += 1
            elif task.status == TaskStatus.RUNNING:
                by_status["running"] += 1
            elif task.status == TaskStatus.COMPLETED:
                by_status["completed"] += 1
            elif task.status == TaskStatus.FAILED:
                by_status["failed"] += 1
            elif task.status == TaskStatus.AWAITING_HUMAN:
                by_status["awaiting_human"] += 1

        by_status["percent"] = int((by_status["completed"] / total) * 100) if total > 0 else 0
        return by_status
