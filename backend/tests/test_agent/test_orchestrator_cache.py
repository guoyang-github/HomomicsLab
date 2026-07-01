"""Tests for Orchestrator workflow-cache integration / incremental execution."""

import pytest

from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.models.common import AgentType, TaskStatus
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.workflow.cache import WorkflowCache


class CountingAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]
    run_count = 0

    async def run(self, task, context):
        CountingAgent.run_count += 1
        return {"status": "success", "output": {"cells": 2700}}


@pytest.fixture
def skill_registry(tmp_path):
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0.0",
            category="test",
            input_schema=SkillInputSchema(),
        )
    )
    return registry


@pytest.fixture
def cache(tmp_path):
    return WorkflowCache(cache_dir=tmp_path / "wf_cache")


@pytest.fixture
def orchestrator(skill_registry, cache):
    registry = AgentRegistry()
    registry.register(CountingAgent())
    CountingAgent.run_count = 0
    return Orchestrator(
        registry=registry,
        skill_registry=skill_registry,
        workflow_cache=cache,
    )


@pytest.mark.asyncio
async def test_cache_hit_skips_execution(orchestrator, cache):
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            parameters={"min_genes": 200},
        ),
    ])

    result1 = await orchestrator.run_tree(tree)
    assert CountingAgent.run_count == 1
    assert result1["t1"]["status"] == "success"
    task1 = tree.get_task("t1")
    assert task1.status == TaskStatus.COMPLETED
    assert task1.cache_hit is False
    assert task1.cache_key is not None

    # Re-run an identical task tree: the agent should not execute again.
    tree2 = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            parameters={"min_genes": 200},
        ),
    ])
    result2 = await orchestrator.run_tree(tree2)
    assert CountingAgent.run_count == 1
    assert result2["t1"]["status"] == "success"
    task2 = tree2.get_task("t1")
    assert task2.status == TaskStatus.COMPLETED
    assert task2.cache_hit is True
    assert task2.cache_key == task1.cache_key


@pytest.mark.asyncio
async def test_cache_miss_on_parameter_change(orchestrator, cache):
    tree1 = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            parameters={"min_genes": 200},
        ),
    ])
    await orchestrator.run_tree(tree1)
    assert CountingAgent.run_count == 1

    tree2 = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            parameters={"min_genes": 500},
        ),
    ])
    await orchestrator.run_tree(tree2)
    assert CountingAgent.run_count == 2
    assert tree2.get_task("t1").cache_hit is False


@pytest.mark.asyncio
async def test_upstream_cache_hit_enables_downstream_cache_hit(orchestrator, cache):
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            parameters={"min_genes": 200},
        ),
        TaskNode(
            id="t2",
            name="normalization",
            description="Normalize",
            skills_required=["scanpy_qc"],
            dependencies=["t1"],
            parameters={"target_sum": 10000},
        ),
    ])

    await orchestrator.run_tree(tree)
    assert CountingAgent.run_count == 2

    tree2 = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            parameters={"min_genes": 200},
        ),
        TaskNode(
            id="t2",
            name="normalization",
            description="Normalize",
            skills_required=["scanpy_qc"],
            dependencies=["t1"],
            parameters={"target_sum": 10000},
        ),
    ])
    await orchestrator.run_tree(tree2)
    assert CountingAgent.run_count == 2
    assert tree2.get_task("t1").cache_hit is True
    assert tree2.get_task("t2").cache_hit is True


@pytest.mark.asyncio
async def test_failed_results_are_not_cached(orchestrator, cache):
    class FailingAgent(BaseAgent):
        agent_type = AgentType.BIOINFO
        capabilities = ["scanpy_qc"]

        async def run(self, task, context):
            raise RuntimeError("boom")

    registry = AgentRegistry()
    registry.register(FailingAgent())
    orch = Orchestrator(
        registry=registry,
        skill_registry=orchestrator.skill_registry,
        workflow_cache=cache,
    )

    tree = TaskTree([
        TaskNode(id="t1", name="quality_control", description="QC", skills_required=["scanpy_qc"]),
    ])

    with pytest.raises(RuntimeError):
        await orch.run_tree(tree)

    task = tree.get_task("t1")
    assert task.status == TaskStatus.FAILED
    # No successful entry should be stored.
    assert cache.get(task.cache_key) is None
