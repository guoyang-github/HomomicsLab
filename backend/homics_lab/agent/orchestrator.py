from typing import Any, Dict
from homics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homics_lab.tasks.task_tree import TaskTree
from homics_lab.hitl.detector import HITLDetector
from homics_lab.models.common import TaskStatus
from homics_lab.tasks.models import TaskNode
from homics_lab.tasks.state_machine import TaskStateMachine


class Orchestrator:
    """Central task scheduler and executor."""

    def __init__(self, registry: AgentRegistry = None):
        self.registry = registry or get_default_registry()
        self.state_machine = TaskStateMachine()
        self.hitl_detector = HITLDetector()

    async def run_tree(self, tree: TaskTree, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        results = {}
        completed = set()

        for task in tree.topological_sort():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.ABORTED):
                completed.add(task.id)
                continue

            # Check dependencies - skip if upstream is blocked (e.g., awaiting HITL)
            if not all(dep in completed for dep in task.dependencies):
                continue

            # Check HITL
            checkpoint = self.hitl_detector.check(task, context)
            if checkpoint:
                self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                results[task.id] = {"hitl": checkpoint.model_dump()}
                continue

            await self._execute_task(task, context, results)
            completed.add(task.id)

        return results

    async def resume_task(
        self,
        tree: TaskTree,
        task_id: str,
        human_response: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        task = tree.get_task(task_id)
        if task.status != TaskStatus.AWAITING_HUMAN:
            raise ValueError(f"Task {task_id} is not awaiting human input")

        # Apply human response to parameters
        if "parameters" in human_response:
            task.parameters.update(human_response["parameters"])

        context = context or {}
        results = {}
        await self._execute_task(task, context, results)

        # Continue with remaining tasks
        remaining_results = await self.run_tree(tree, context)
        results.update(remaining_results)

        return results

    async def _execute_task(self, task: TaskNode, context: Dict[str, Any], results: Dict[str, Any]) -> None:
        max_attempts = task.retry_policy.max_attempts
        backoff = task.retry_policy.backoff_seconds

        for attempt in range(1, max_attempts + 1):
            # Only transition if not already running (e.g., on retry)
            if task.status != TaskStatus.RUNNING:
                self.state_machine.transition(task, TaskStatus.RUNNING)

            try:
                agent = self._resolve_agent(task)
                if agent is None:
                    raise RuntimeError(f"No agent found for task {task.name}")

                result = await agent.run(task, context)
                results[task.id] = result
                task.result = result
                self.state_machine.transition(task, TaskStatus.COMPLETED)
                return

            except Exception as e:
                task.error_message = str(e)
                task.attempt_count = attempt

                if attempt < max_attempts:
                    # Transition to FAILED so we can retry
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    # Retry with backoff
                    import asyncio
                    await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                else:
                    # Final attempt failed
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    raise

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
            "aborted": 0,
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
            elif task.status == TaskStatus.ABORTED:
                by_status["aborted"] += 1

        by_status["percent"] = int((by_status["completed"] / total) * 100) if total > 0 else 0
        return by_status
