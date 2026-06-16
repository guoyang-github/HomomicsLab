"""Tests for the Orchestrator task scheduler."""

import pytest

from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.phase_gate import PhaseGateEvaluator
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.models.common import AgentType, HITLTrigger, TaskStatus
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import EdgeStatus, EdgeType, SkillDAG
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


class FakeBioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]

    async def run(self, task, context):
        return {"output_file": "qc_result.h5ad"}


class FakeQCFailAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]

    async def run(self, task, context):
        return {"result": {"qc": {"pass_rate": 0.2}}}


class FakeMultiSkillAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc", "scanpy_normalize"]

    async def run(self, task, context):
        output = {"input_cells": 2700, "output_cells": 2531}
        if task.name == "normalization":
            output = {"normalized": True}
        return {"status": "success", "output": output}


@pytest.fixture
def orchestrator():
    registry = AgentRegistry()
    registry.register(FakeBioinfoAgent())
    return Orchestrator(registry=registry)


@pytest.fixture
def gated_orchestrator():
    registry = AgentRegistry()
    registry.register(FakeQCFailAgent())
    plan_engine = TaskDecomposer()._get_plan_engine()
    return Orchestrator(
        registry=registry,
        phase_gate_evaluator=PhaseGateEvaluator(),
        replanning_engine=DynamicReplanningEngine(plan_engine=plan_engine),
    )


@pytest.mark.asyncio
async def test_orchestrator_can_run_task(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="quality_control", description="QC", skills_required=["scanpy_qc"]),
    ])

    result = await orchestrator.run_tree(tree)

    assert result["t1"]["output_file"] == "qc_result.h5ad"
    task = tree.get_task("t1")
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_orchestrator_respects_dependencies(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="step1", description="step 1", skills_required=["scanpy_qc"]),
        TaskNode(id="t2", name="step2", description="step 2", skills_required=["scanpy_qc"], dependencies=["t1"]),
    ])

    result = await orchestrator.run_tree(tree)

    assert "t1" in result
    assert "t2" in result
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
    assert tree.get_task("t2").status == TaskStatus.COMPLETED


def test_orchestrator_progress(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="step1", description="step 1"),
        TaskNode(id="t2", name="step2", description="step 2", dependencies=["t1"]),
    ])

    progress = orchestrator.get_progress(tree)
    assert progress["total"] == 2
    assert progress["pending"] == 2
    assert progress["completed"] == 0


@pytest.mark.asyncio
async def test_gate_pass_marks_task_completed(orchestrator):
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            success_criteria=[
                {
                    "metric": "output_file",
                    "operator": "==",
                    "threshold": "qc_result.h5ad",
                }
            ],
        ),
    ])

    result = await orchestrator.run_tree(tree)
    assert result["t1"]["output_file"] == "qc_result.h5ad"
    assert tree.get_task("t1").status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_gate_fail_escalates_to_hitl(gated_orchestrator):
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            success_criteria=[
                {
                    "metric": "result.qc.pass_rate",
                    "operator": ">=",
                    "threshold": 0.4,
                    "on_failure": "hitl",
                }
            ],
        ),
    ])

    result = await gated_orchestrator.run_tree(tree)

    task = tree.get_task("t1")
    assert task.status == TaskStatus.AWAITING_HUMAN
    assert "hitl" in result["t1"]
    assert result["t1"]["hitl"]["trigger_reason"] == HITLTrigger.PHASE_GATE_FAIL


@pytest.mark.asyncio
async def test_gate_fail_auto_replan_inserts_remediation():
    registry = AgentRegistry()
    registry.register(FakeQCFailAgent())
    plan_engine = TaskDecomposer()._get_plan_engine()
    orchestrator = Orchestrator(
        registry=registry,
        phase_gate_evaluator=PhaseGateEvaluator(),
        replanning_engine=DynamicReplanningEngine(plan_engine=plan_engine),
        interpretation_engine=None,
    )
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            phase="preprocessing",
            skills_required=["scanpy_qc"],
            success_criteria=[
                {
                    "metric": "result.qc.pass_rate",
                    "operator": ">=",
                    "threshold": 0.4,
                    "on_failure": "replan",
                }
            ],
        ),
    ])

    result = await orchestrator.run_tree(tree)

    task_names = [t.name for t in tree.tasks]
    assert "quality_control" in task_names
    assert "qc" in task_names
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
    assert any(t.name == "qc" and t.status == TaskStatus.COMPLETED for t in tree.tasks)
    assert "t1" in result


@pytest.mark.asyncio
async def test_adaptive_replan_inserts_downstream_phase(tmp_path):
    skill_registry = SkillRegistry()
    skill_registry.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(),
        )
    )
    skill_registry.register(
        SkillDefinition(
            id="scanpy_normalize",
            name="scanpy_normalize",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(),
        )
    )
    skill_dag = SkillDAG(registry=skill_registry, db_path=tmp_path / "dag.db")
    skill_dag.propose_edge("scanpy_qc", "scanpy_normalize", EdgeType.FOLLOWED_BY)
    edge = skill_dag.edges["scanpy_qc_followed_by_scanpy_normalize"]
    edge.status = EdgeStatus.CONFIRMED
    edge.confidence = 0.85

    agent_registry = AgentRegistry()
    agent_registry.register(FakeMultiSkillAgent())

    plan_engine = PlanEngine(skill_registry=skill_registry, skill_dag=skill_dag)
    orchestrator = Orchestrator(
        registry=agent_registry,
        replanning_engine=DynamicReplanningEngine(plan_engine=plan_engine, skill_dag=skill_dag),
    )

    tree = TaskTree([
        TaskNode(id="t1", name="qc", description="QC", skills_required=["scanpy_qc"]),
    ])

    result = await orchestrator.run_tree(tree)

    task_names = [t.name for t in tree.tasks]
    assert "qc" in task_names
    assert "normalization" in task_names
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
    assert result["t1"]["status"] == "success"
