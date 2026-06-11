"""AgentSwarm — multi-agent collaboration with parallel execution and consensus voting."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.agent.core import AgentCore, DynamicAgent
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.models.common import AgentMessage, TaskStatus
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@dataclass
class ParallelTaskGroup:
    """A group of tasks that can be executed in parallel."""

    task_group_id: str
    tasks: List[Any]
    max_parallelism: int = 3
    consensus_required: bool = False


@dataclass
class TaskAssignment:
    """Mapping of a task to an agent."""

    task: Any
    agent_name: str
    role_id: str


@dataclass
class SwarmResult:
    """Result of a swarm execution or consensus vote."""

    results: Dict[str, Dict] = field(default_factory=dict)
    consensus_reached: bool = False
    dissenting_opinions: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class AgentSwarm:
    """Executes tasks in parallel and coordinates consensus voting."""

    def __init__(self, agent_core: AgentCore, max_parallelism: int = 3):
        self.agent_core = agent_core
        self.max_parallelism = max_parallelism

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------
    async def execute_parallel(self, task_group: ParallelTaskGroup) -> SwarmResult:
        """Execute a group of tasks in parallel with a semaphore limit."""
        start = time.perf_counter()
        semaphore = asyncio.Semaphore(task_group.max_parallelism)

        # Resolve agent for each task and build assignments
        resolved: List[tuple] = []
        for task in task_group.tasks:
            agent = self.agent_core.resolve_agent_for_task(task)
            if agent is None:
                raise RuntimeError(
                    f"No agent found for task {getattr(task, 'name', task)}"
                )
            resolved.append((task, agent))

        async def _run_one(task: Any, agent: DynamicAgent) -> tuple:
            async with semaphore:
                context: Dict[str, Any] = {}
                result = await agent.run(task, context)
                task_id = task.id if hasattr(task, "id") else str(task)
                return task_id, result

        coros = [_run_one(task, agent) for task, agent in resolved]
        outputs = await asyncio.gather(*coros, return_exceptions=True)

        results: Dict[str, Dict] = {}
        for item in outputs:
            if isinstance(item, Exception):
                raise item
            task_id, result = item
            results[task_id] = result

        consensus_reached = False
        dissenting_opinions: List[str] = []
        if task_group.consensus_required:
            consensus_reached, dissenting_opinions = self._evaluate_consensus(results)

        duration_ms = (time.perf_counter() - start) * 1000
        return SwarmResult(
            results=results,
            consensus_reached=consensus_reached,
            dissenting_opinions=dissenting_opinions,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Consensus voting
    # ------------------------------------------------------------------
    async def consensus_vote(
        self,
        task: Any,
        agents: List[DynamicAgent],
        context: Dict[str, Any],
    ) -> SwarmResult:
        """Run the same task on multiple agents and compare outputs."""
        start = time.perf_counter()

        async def _run_one(agent: DynamicAgent) -> tuple:
            result = await agent.run(task, context)
            return agent.name, result

        outputs = await asyncio.gather(*[_run_one(agent) for agent in agents])
        results = {name: result for name, result in outputs}

        consensus_reached, dissenting_opinions = self._evaluate_consensus(results)
        duration_ms = (time.perf_counter() - start) * 1000

        return SwarmResult(
            results=results,
            consensus_reached=consensus_reached,
            dissenting_opinions=dissenting_opinions,
            duration_ms=duration_ms,
        )

    def _evaluate_consensus(self, results: Dict[str, Dict]) -> tuple:
        """Compare outputs using dict equality + key overlap scoring."""
        if len(results) <= 1:
            return True, []

        def _similarity(a: Any, b: Any) -> float:
            if not isinstance(a, dict) or not isinstance(b, dict):
                return 1.0 if a == b else 0.0
            if a == b:
                return 1.0
            keys_a = set(a.keys())
            keys_b = set(b.keys())
            if not keys_a or not keys_b:
                return 0.0
            key_overlap = len(keys_a & keys_b) / len(keys_a | keys_b)
            shared = keys_a & keys_b
            if not shared:
                return 0.0
            value_agree = sum(1 for k in shared if a[k] == b[k]) / len(shared)
            return 0.5 * key_overlap + 0.5 * value_agree

        # Cluster results by similarity (>= 0.8 key overlap)
        clusters: List[List[tuple]] = []
        for agent_name, result in results.items():
            placed = False
            for cluster in clusters:
                rep = cluster[0][1]
                if _similarity(rep, result) >= 0.8:
                    cluster.append((agent_name, result))
                    placed = True
                    break
            if not placed:
                clusters.append([(agent_name, result)])

        majority_cluster = max(clusters, key=len)
        majority_threshold = len(results) / 2
        consensus_reached = len(majority_cluster) > majority_threshold

        if consensus_reached:
            majority_agents = {name for name, _ in majority_cluster}
            dissenting = [name for name in results if name not in majority_agents]
            return True, dissenting

        return False, list(results.keys())

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------
    def broadcast(
        self, message: str, to_roles: Optional[List[str]] = None
    ) -> List[AgentMessage]:
        """Send a message to all agents matching the given roles."""
        messages: List[AgentMessage] = []
        all_agents: List[DynamicAgent] = []

        analyst = self.agent_core.get_analyst()
        if analyst is not None:
            all_agents.append(analyst)

        for agent in self.agent_core.list_specialists():
            if agent not in all_agents:
                all_agents.append(agent)

        # Pull any extra agents from the agent_registry that aren't already listed
        for agent in self.agent_core.agent_registry.list_agents():
            if agent not in all_agents and isinstance(agent, DynamicAgent):
                all_agents.append(agent)

        for agent in all_agents:
            if to_roles is None or agent.role.role_id in to_roles:
                msg = agent.send_message(to_agent="broadcast", content=message)
                messages.append(msg)

        return messages


class SwarmOrchestrator(Orchestrator):
    """Orchestrator that adds parallel tree execution via AgentSwarm."""

    def __init__(self, orchestrator: Orchestrator, swarm: AgentSwarm):
        self.registry = orchestrator.registry
        self.state_machine = orchestrator.state_machine
        self.hitl_detector = orchestrator.hitl_detector
        self.swarm = swarm

    async def run_tree_parallel(
        self, tree: TaskTree, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a task tree in parallel groups, respecting dependencies."""
        context = context or {}
        results: Dict[str, Any] = {}
        completed: set = set()

        remaining = list(tree.tasks)

        while remaining:
            # Identify independent tasks (all deps completed)
            ready: List[TaskNode] = []
            for task in remaining[:]:
                if task.status in (TaskStatus.COMPLETED, TaskStatus.ABORTED):
                    completed.add(task.id)
                    remaining.remove(task)
                    continue

                if all(dep in completed for dep in task.dependencies):
                    ready.append(task)
                    remaining.remove(task)

            if not ready:
                if remaining:
                    raise ValueError("Cyclic dependency detected or tasks blocked")
                break

            for task in ready:
                self.state_machine.transition(task, TaskStatus.RUNNING)

            group = ParallelTaskGroup(
                task_group_id=f"group_{len(results)}",
                tasks=ready,
                max_parallelism=self.swarm.max_parallelism,
                consensus_required=False,
            )

            swarm_result = await self.swarm.execute_parallel(group)

            for task_id, result in swarm_result.results.items():
                results[task_id] = result
                task = tree.get_task(task_id)
                task.result = result
                self.state_machine.transition(task, TaskStatus.COMPLETED)
                completed.add(task_id)

        return results
