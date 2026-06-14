"""Tests for Supervisor-Worker-Reviewer (SWR) collaboration."""

import pytest

from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.core import AgentCore, RoleDefinition, RolePermissions, RoleRegistry
from homomics_lab.agent.core.dynamic_agent import DynamicAgent
from homomics_lab.agent.message_bus import AgentMessageBus
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine
from homomics_lab.agent.reviewer import ReviewerAgent
from homomics_lab.agent.supervisor import SupervisorAgent
from homomics_lab.agent.worker import WorkerAgent
from homomics_lab.models.common import AgentType, HITLTrigger, TaskStatus
from homomics_lab.tasks.models import RetryPolicy, TaskNode
from homomics_lab.tasks.task_tree import TaskTree


class FakeSkillExecutor:
    def __init__(self, fail_skill=None):
        self.fail_skill = fail_skill
        self.calls = []

    async def execute(self, skill_id, params):
        self.calls.append((skill_id, params))
        if skill_id == self.fail_skill:
            raise RuntimeError(f"skill {skill_id} failed")
        return {"skill_id": skill_id, "params": params, "qc": {"pass_rate": 0.9}}


@pytest.fixture
def role_registry():
    reg = RoleRegistry()
    reg.register(
        RoleDefinition(
            role_id="analyst",
            name="Analyst",
            agent_type="bioinfo",
            allowed_skills=["*"],
            permissions=RolePermissions(can_spawn_specialist=True),
            priority=10,
        )
    )
    reg.register(
        RoleDefinition(
            role_id="viz",
            name="Viz",
            agent_type="viz",
            allowed_skills=["plot_umap"],
            priority=50,
        )
    )
    reg.register(
        RoleDefinition(
            role_id="worker",
            name="Worker",
            agent_type="worker",
            allowed_skills=["*"],
            permissions=RolePermissions(can_execute=True),
            tags=["system"],
        )
    )
    reg.register(
        RoleDefinition(
            role_id="reviewer",
            name="Reviewer",
            agent_type="reviewer",
            allowed_skills=[],
            permissions=RolePermissions(can_review=True),
            tags=["system"],
        )
    )
    reg.register(
        RoleDefinition(
            role_id="supervisor",
            name="Supervisor",
            agent_type="supervisor",
            allowed_skills=[],
            permissions=RolePermissions(can_delegate=True, can_review=True),
            tags=["system"],
        )
    )
    return reg


@pytest.fixture
def agent_registry():
    return AgentRegistry()


@pytest.fixture
def agent_core(role_registry, agent_registry):
    return AgentCore(
        role_registry=role_registry,
        agent_registry=agent_registry,
    )


@pytest.fixture
def swr_agents(role_registry, agent_registry):
    """Create and register Supervisor, Worker, Reviewer with a fake executor."""
    executor = FakeSkillExecutor()
    worker = WorkerAgent(
        role=role_registry.get("worker"),
        skill_executor=executor,
    )
    reviewer = ReviewerAgent(
        role=role_registry.get("reviewer"),
        skill_executor=executor,
    )
    agent_core = AgentCore(
        role_registry=role_registry,
        agent_registry=agent_registry,
        skill_executor=executor,
    )
    agent_core.init_analyst()
    agent_registry.register(worker)
    agent_registry.register(reviewer)
    supervisor = SupervisorAgent(
        role=role_registry.get("supervisor"),
        agent_core=agent_core,
        skill_executor=executor,
    )
    agent_registry.register(supervisor)
    return supervisor, worker, reviewer, executor


@pytest.mark.asyncio
async def test_delegate_to_worker(agent_core, agent_registry, role_registry):
    agent_core.init_analyst()
    worker = WorkerAgent(
        role=role_registry.get("worker"),
        skill_executor=FakeSkillExecutor(),
    )
    agent_registry.register(worker)
    supervisor = SupervisorAgent(
        role=role_registry.get("supervisor"),
        agent_core=agent_core,
    )
    agent_registry.register(supervisor)

    task = TaskNode(
        id="t1",
        name="plot",
        description="plot umap",
        skills_required=["plot_umap"],
        agent_assignment=AgentType.WORKER,
    )
    agent = await supervisor.delegate(task, {})
    assert isinstance(agent, DynamicAgent)
    assert agent.agent_type == AgentType.WORKER


@pytest.mark.asyncio
async def test_worker_returns_structured_result(role_registry):
    executor = FakeSkillExecutor()
    worker = WorkerAgent(
        role=role_registry.get("worker"),
        skill_executor=executor,
    )
    task = TaskNode(
        id="t1",
        name="qc",
        description="run qc",
        skills_required=["scanpy_qc"],
    )
    result = await worker.run(task, {})
    assert result["status"] == "success"
    assert result["output"]["skill"] == "scanpy_qc"
    assert result["execution_time_seconds"] >= 0
    assert result["task_id"] == "t1"


@pytest.mark.asyncio
async def test_worker_returns_failure_on_exception(role_registry):
    executor = FakeSkillExecutor(fail_skill="scanpy_qc")
    worker = WorkerAgent(
        role=role_registry.get("worker"),
        skill_executor=executor,
    )
    task = TaskNode(
        id="t1",
        name="qc",
        description="run qc",
        skills_required=["scanpy_qc"],
    )
    result = await worker.run(task, {})
    assert result["status"] == "failure"
    assert "scanpy_qc failed" in result["error"]


@pytest.mark.asyncio
async def test_reviewer_rejects_custom_clustering(role_registry):
    reviewer = ReviewerAgent(role=role_registry.get("reviewer"))
    task = TaskNode(
        id="t1",
        name="cluster",
        description="cluster cells",
        phase="clustering",
        parameters={"n_neighbors": 20},
        skills_required=["scanpy_cluster"],
    )
    decision = await reviewer.review(task, {"status": "success", "output": {}})
    assert decision["approved"] is False
    assert decision["action"] == "hitl"
    assert "clustering" in decision["reason"]


@pytest.mark.asyncio
async def test_reviewer_approves_qc(role_registry):
    reviewer = ReviewerAgent(role=role_registry.get("reviewer"))
    task = TaskNode(
        id="t1",
        name="qc",
        description="run qc",
        phase="qc",
        skills_required=["scanpy_qc"],
    )
    decision = await reviewer.review(task, {"status": "success", "output": {}})
    assert decision["approved"] is True
    assert decision["action"] == "proceed"


def test_handle_worker_failure_decisions():
    role = RoleDefinition(role_id="supervisor", name="Supervisor", agent_type="supervisor")
    supervisor = SupervisorAgent(role=role)
    task = TaskNode(
        id="t1",
        name="qc",
        description="run qc",
        retry_policy=RetryPolicy(max_attempts=2),
        max_replan_attempts=2,
        replan_attempt_count=0,
    )
    assert supervisor.handle_worker_failure(task, 1)["action"] == "retry"
    assert supervisor.handle_worker_failure(task, 2)["action"] == "replan"

    task.replan_attempt_count = 2
    assert supervisor.handle_worker_failure(task, 2)["action"] == "hitl"


@pytest.mark.asyncio
async def test_orchestrator_worker_failure_replans(swr_agents):
    supervisor, worker, reviewer, executor = swr_agents
    executor.fail_skill = "scanpy_qc"

    tree = TaskTree(
        [
            TaskNode(
                id="qc1",
                name="qc",
                description="run qc",
                skills_required=["scanpy_qc"],
                retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0.01),
                max_replan_attempts=2,
            )
        ]
    )

    # Fake replanning engine: insert a remediation phase after the failed one.
    class FakeReplanEngine:
        def replan(self, current_plan, triggers, data_state):
            from homomics_lab.agent.plan.models import Phase, PlanResult

            phases = list(current_plan.phases)
            phases.insert(1, Phase(phase_type="remediation", description="fix qc"))
            return PlanResult(
                phases=phases,
                strategy_name="replan",
                data_state=current_plan.data_state,
            )

    orchestrator = Orchestrator(
        registry=AgentRegistry(),  # not used; agents come from supervisor
        supervisor=supervisor,
        reviewer=reviewer,
        replanning_engine=FakeReplanEngine(),
    )

    results = await orchestrator.run_tree(tree)
    # After failure, the Orchestrator replans and the failed task is completed.
    qc_task = tree.get_task("qc1")
    assert qc_task.status == TaskStatus.COMPLETED
    assert qc_task.replan_attempt_count == 1
    assert any(t.name == "remediation" for t in tree.tasks)
    assert "qc1" in results


@pytest.mark.asyncio
async def test_orchestrator_replan_exhaustion_escalates_hitl(swr_agents):
    supervisor, worker, reviewer, executor = swr_agents
    executor.fail_skill = "scanpy_qc"

    tree = TaskTree(
        [
            TaskNode(
                id="qc1",
                name="qc",
                description="run qc",
                skills_required=["scanpy_qc"],
                retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0.01),
                max_replan_attempts=0,
            )
        ]
    )

    orchestrator = Orchestrator(
        supervisor=supervisor,
        reviewer=reviewer,
        replanning_engine=DynamicReplanningEngine(plan_engine=None, skill_dag=None),
    )

    results = await orchestrator.run_tree(tree)
    assert results["qc1"]["hitl"]["trigger_reason"] == HITLTrigger.WORKER_FAILURE


@pytest.mark.asyncio
async def test_orchestrator_reviewer_hitl_for_clustering(swr_agents):
    supervisor, worker, reviewer, executor = swr_agents

    tree = TaskTree(
        [
            TaskNode(
                id="c1",
                name="cluster",
                description="cluster cells",
                phase="clustering",
                parameters={"resolution": 0.8},
                skills_required=["scanpy_cluster"],
            )
        ]
    )

    orchestrator = Orchestrator(
        supervisor=supervisor,
        reviewer=reviewer,
    )

    results = await orchestrator.run_tree(tree)
    assert results["c1"]["hitl"]["trigger_reason"] == HITLTrigger.REVIEWER_REJECT


@pytest.mark.asyncio
async def test_message_bus_records_swr_events(swr_agents):
    supervisor, worker, reviewer, executor = swr_agents
    bus = AgentMessageBus()
    supervisor.message_bus = bus
    worker.message_bus = bus
    reviewer.message_bus = bus

    events = []
    bus.subscribe("swr", lambda topic, msg: events.append((msg.from_agent, msg.content)))

    task = TaskNode(
        id="qc1",
        name="qc",
        description="run qc",
        skills_required=["scanpy_qc"],
    )
    await supervisor.delegate(task, {})
    await worker.run(task, {})
    await reviewer.review(task, {"status": "success", "output": {}})

    assert any("delegate" in content for _, content in events)
    assert any("worker_complete" in content for _, content in events)
    assert any("review_complete" in content for _, content in events)
