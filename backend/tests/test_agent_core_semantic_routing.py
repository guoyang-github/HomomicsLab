"""Tests for AgentCore semantic-search task routing (P4-2)."""

import pytest

from homomics_lab.agent.core.agent_core import AgentCore
from homomics_lab.agent.core.role import RoleDefinition
from homomics_lab.skills.models import SkillDefinition, SkillResources, SkillRuntime
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG
from homomics_lab.tasks.models import TaskNode


@pytest.fixture
def registry_with_skills():
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id="scanpy_qc",
            name="Quality Control",
            description="Filter low quality cells and genes",
            version="1.0",
            category="single-cell",
            author="test",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="1GB", cpu=1, time="5m"),
            ),
        )
    )
    registry.register(
        SkillDefinition(
            id="plot_umap",
            name="UMAP Plot",
            description="Visualize cells with UMAP",
            version="1.0",
            category="single-cell",
            author="test",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="1GB", cpu=1, time="5m"),
            ),
        )
    )
    return registry


@pytest.fixture
def agent_core(registry_with_skills):
    skill_dag = SkillDAG(registry=registry_with_skills)
    role_registry = agent_core_role_registry()
    return AgentCore(role_registry=role_registry, skill_dag=skill_dag)


def agent_core_role_registry():
    from homomics_lab.agent.core.registry import RoleRegistry

    reg = RoleRegistry()
    reg.register(
        RoleDefinition(
            role_id="analyst",
            name="Analyst",
            description="Coordinator",
            agent_type="bioinfo",
            permissions={"can_execute": True},
        )
    )
    reg.register(
        RoleDefinition(
            role_id="viz_specialist",
            name="Visualization Specialist",
            description="Plots",
            agent_type="viz",
            allowed_skills=["plot_umap"],
            permissions={"can_execute": True},
        )
    )
    return reg


class TestAgentCoreSemanticRouting:
    def test_resolves_skill_from_description(self, agent_core, registry_with_skills):
        task = TaskNode(
            id="task_1",
            name="visualize",
            description="visualize cells using UMAP",
            skills_required=[],
        )
        agent = agent_core.resolve_agent_for_task(task)
        assert agent is not None
        assert agent.can_handle("plot_umap")

    def test_explicit_skill_takes_priority(self, agent_core):
        task = TaskNode(
            id="task_1",
            name="qc",
            description="visualize cells using UMAP",
            skills_required=["scanpy_qc"],
        )
        agent = agent_core.resolve_agent_for_task(task)
        assert agent is not None
        assert agent.can_handle("scanpy_qc")

    def test_no_match_returns_none(self, agent_core):
        task = TaskNode(
            id="task_1",
            name="unknown",
            description="xyz_unknown_task",
            skills_required=[],
        )
        agent = agent_core.resolve_agent_for_task(task)
        assert agent is None
