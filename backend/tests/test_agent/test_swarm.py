import asyncio
import pytest

from homomics_lab.agent.swarm import (
    AgentSwarm,
    ParallelTaskGroup,
    SwarmOrchestrator,
    SwarmResult,
)
from homomics_lab.agent.core import AgentCore, DynamicAgent, RoleDefinition
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.models.common import TaskStatus
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_role(role_id: str, name: str) -> RoleDefinition:
    return RoleDefinition(
        role_id=role_id,
        name=name,
        description=f"Role {role_id}",
        allowed_skills=["*"],
    )


def _make_agent(name: str, role_id: str) -> DynamicAgent:
    role = _make_role(role_id, name)
    return DynamicAgent(role=role, name=name)


@pytest.fixture
def agent_core() -> AgentCore:
    core = AgentCore(agent_registry=AgentRegistry())
    # Init analyst so it exists for broadcast tests
    core.init_analyst()
    # Register roles before spawning specialists
    for role_id in ("bioinfo", "viz", "qa"):
        core.role_registry.register(_make_role(role_id, role_id.capitalize()))
    core.spawn_specialist("bioinfo", name="BioAgent")
    core.spawn_specialist("viz", name="VizAgent")
    core.spawn_specialist("qa", name="QAAgent")
    return core


@pytest.fixture
def swarm(agent_core: AgentCore) -> AgentSwarm:
    return AgentSwarm(agent_core=agent_core, max_parallelism=3)


@pytest.fixture
def orchestrator(agent_core: AgentCore) -> Orchestrator:
    registry = agent_core.agent_registry
    return Orchestrator(registry=registry)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_execution(swarm: AgentSwarm, agent_core: AgentCore):
    """Tasks in a group should execute in parallel and return aggregated results."""
    tasks = [
        TaskNode(id="t1", name="task1", description="d1", skills_required=["scanpy_qc"]),
        TaskNode(id="t2", name="task2", description="d2", skills_required=["scanpy_cluster"]),
    ]
    group = ParallelTaskGroup(task_group_id="g1", tasks=tasks, max_parallelism=2)

    result = await swarm.execute_parallel(group)

    assert isinstance(result, SwarmResult)
    assert "t1" in result.results
    assert "t2" in result.results
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_consensus_vote_agreement(swarm: AgentSwarm):
    """When all agents agree, consensus is reached with no dissent."""
    agents = [
        _make_agent("AgentA", "bioinfo"),
        _make_agent("AgentB", "bioinfo"),
        _make_agent("AgentC", "bioinfo"),
    ]
    task = TaskNode(id="c1", name="consensus_task", description="d")

    # Override run() so every agent returns the exact same dict
    for agent in agents:
        agent.run = lambda _task, _ctx: asyncio.sleep(0, result={"answer": 42})  # type: ignore[assignment]

    result = await swarm.consensus_vote(task, agents, context={})

    assert result.consensus_reached is True
    assert result.dissenting_opinions == []
    assert len(result.results) == 3


@pytest.mark.asyncio
async def test_consensus_vote_dissent(swarm: AgentSwarm):
    """When one agent disagrees, consensus may still be reached with dissent recorded."""
    agents = [
        _make_agent("AgentA", "bioinfo"),
        _make_agent("AgentB", "bioinfo"),
        _make_agent("AgentC", "bioinfo"),
    ]
    task = TaskNode(id="c1", name="consensus_task", description="d")

    async def _run_a(_task, _ctx):
        return {"answer": 42}

    async def _run_b(_task, _ctx):
        return {"answer": 42}

    async def _run_c(_task, _ctx):
        return {"answer": 99}

    agents[0].run = _run_a  # type: ignore[assignment]
    agents[1].run = _run_b  # type: ignore[assignment]
    agents[2].run = _run_c  # type: ignore[assignment]

    result = await swarm.consensus_vote(task, agents, context={})

    assert result.consensus_reached is True
    assert "AgentC" in result.dissenting_opinions
    assert len(result.dissenting_opinions) == 1


@pytest.mark.asyncio
async def test_semaphore_limits_parallelism(agent_core: AgentCore):
    """The semaphore should cap the number of concurrently running tasks."""
    max_parallel = 2
    swarm = AgentSwarm(agent_core=agent_core, max_parallelism=max_parallel)

    concurrently_running = 0
    max_observed = 0
    lock = asyncio.Lock()

    async def _tracking_run(_task, _ctx):
        nonlocal concurrently_running, max_observed
        async with lock:
            concurrently_running += 1
            max_observed = max(max_observed, concurrently_running)
        await asyncio.sleep(0.05)
        async with lock:
            concurrently_running -= 1
        return {"done": True}

    # Create a few agents and override their run methods
    agents = [
        _make_agent(f"Agent{i}", "bioinfo") for i in range(4)
    ]
    for agent in agents:
        agent.run = _tracking_run  # type: ignore[assignment]

    # Register agents so resolve_agent_for_task can find them
    for agent in agents:
        agent_core.agent_registry.register(agent)

    tasks = [
        TaskNode(id=f"t{i}", name=f"task{i}", description="d", skills_required=["scanpy_qc"])
        for i in range(4)
    ]
    group = ParallelTaskGroup(task_group_id="g1", tasks=tasks, max_parallelism=max_parallel)

    await swarm.execute_parallel(group)

    assert max_observed <= max_parallel


@pytest.mark.asyncio
async def test_broadcast(swarm: AgentSwarm, agent_core: AgentCore):
    """Broadcast should send messages to all agents matching the specified roles."""
    messages = swarm.broadcast("hello world", to_roles=["bioinfo", "viz"])

    # Should get one message per matching agent
    sender_names = {msg.from_agent for msg in messages}
    assert "BioAgent" in sender_names
    assert "VizAgent" in sender_names
    assert "QAAgent" not in sender_names
    for msg in messages:
        assert msg.content == "hello world"
        assert msg.to_agent == "broadcast"

    # Broadcast to all roles
    all_messages = swarm.broadcast("global")
    all_senders = {msg.from_agent for msg in all_messages}
    assert "BioAgent" in all_senders
    assert "VizAgent" in all_senders
    assert "QAAgent" in all_senders
    # Analyst is also present
    assert agent_core.get_analyst().name in all_senders


@pytest.mark.asyncio
async def test_run_tree_parallel(swarm: AgentSwarm, orchestrator: Orchestrator):
    """SwarmOrchestrator should execute independent tasks in parallel and respect dependencies."""
    tree = TaskTree([
        TaskNode(id="t1", name="step1", description="d1", skills_required=["scanpy_qc"]),
        TaskNode(id="t2", name="step2", description="d2", skills_required=["scanpy_qc"]),
        TaskNode(id="t3", name="step3", description="d3", skills_required=["scanpy_qc"], dependencies=["t1", "t2"]),
    ])

    swarm_orch = SwarmOrchestrator(orchestrator=orchestrator, swarm=swarm)
    result = await swarm_orch.run_tree_parallel(tree)

    assert "t1" in result
    assert "t2" in result
    assert "t3" in result
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
    assert tree.get_task("t2").status == TaskStatus.COMPLETED
    assert tree.get_task("t3").status == TaskStatus.COMPLETED
