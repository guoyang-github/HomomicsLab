"""Tests for AgentCore — dynamic role injection system."""

import pytest

from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.agent.core import AgentCore, DynamicAgent, RoleDefinition, RolePermissions, RoleRegistry
from homomics_lab.models.common import AgentType


class FakeTask:
    def __init__(self, name, skills=None, agent_assignment=None):
        self.name = name
        self.skills_required = skills or []
        self.agent_assignment = agent_assignment
        self.parameters = {}


class FakeSkillExecutor:
    async def execute(self, skill_id, params):
        return {"skill_id": skill_id, "params": params}


@pytest.fixture
def role_registry():
    reg = RoleRegistry()
    reg.register(RoleDefinition(
        role_id="analyst",
        name="Analyst",
        agent_type="bioinfo",
        allowed_skills=["*"],
        permissions=RolePermissions(can_spawn_specialist=True),
        priority=10,
    ))
    reg.register(RoleDefinition(
        role_id="viz",
        name="Viz",
        agent_type="viz",
        allowed_skills=["plot_umap", "plot_heatmap"],
        priority=50,
    ))
    reg.register(RoleDefinition(
        role_id="qc",
        name="QC Specialist",
        agent_type="bioinfo",
        allowed_skills=["scanpy_qc", "scanpy_filter"],
        allowed_skill_categories=["preprocessing"],
        priority=30,
    ))
    return reg


@pytest.fixture
def agent_core(role_registry):
    return AgentCore(
        role_registry=role_registry,
        skill_executor=FakeSkillExecutor(),
    )


class TestRoleDefinition:

    def test_can_handle_skill_exact(self):
        role = RoleDefinition(
            role_id="r1",
            name="R1",
            allowed_skills=["scanpy_qc"],
        )
        assert role.can_handle_skill("scanpy_qc") is True
        assert role.can_handle_skill("plot_umap") is False

    def test_can_handle_skill_wildcard(self):
        role = RoleDefinition(
            role_id="r1",
            name="R1",
            allowed_skills=["scanpy_*"],
        )
        assert role.can_handle_skill("scanpy_qc") is True
        assert role.can_handle_skill("scanpy_cluster") is True
        assert role.can_handle_skill("plot_umap") is False

    def test_can_handle_skill_blocked(self):
        role = RoleDefinition(
            role_id="r1",
            name="R1",
            allowed_skills=["scanpy_*"],
            blocked_skills=["scanpy_de"],
        )
        assert role.can_handle_skill("scanpy_qc") is True
        assert role.can_handle_skill("scanpy_de") is False

    def test_can_handle_skill_category(self):
        role = RoleDefinition(
            role_id="r1",
            name="R1",
            allowed_skill_categories=["preprocessing"],
        )
        assert role.can_handle_skill("x", skill_category="preprocessing") is True
        assert role.can_handle_skill("x", skill_category="analysis") is False

    def test_generalist_no_allowlist(self):
        role = RoleDefinition(role_id="r1", name="R1")
        assert role.can_handle_skill("anything") is True

    def test_match_score_priority(self):
        role = RoleDefinition(
            role_id="r1",
            name="R1",
            allowed_skills=["scanpy_qc"],
            priority=10,
        )
        assert role.match_score("scanpy_qc") > role.match_score("other")
        assert role.match_score("other") == -1

    def test_can_use_tool(self):
        role = RoleDefinition(
            role_id="r1",
            name="R1",
            allowed_tools=["file_read"],
        )
        assert role.can_use_tool("file_read") is True
        assert role.can_use_tool("shell_exec") is False

    def test_can_use_tool_no_restrictions(self):
        role = RoleDefinition(role_id="r1", name="R1")
        assert role.can_use_tool("anything") is True


class TestRoleRegistry:

    def test_register_and_get(self):
        reg = RoleRegistry()
        role = RoleDefinition(role_id="r1", name="R1")
        reg.register(role)
        assert reg.get("r1") == role
        assert reg.get("missing") is None

    def test_find_for_skill(self):
        reg = RoleRegistry()
        reg.register(RoleDefinition(role_id="viz", name="Viz", allowed_skills=["plot_umap"], priority=50))
        reg.register(RoleDefinition(role_id="bio", name="Bio", allowed_skills=["scanpy_qc"], priority=10))

        results = reg.find_for_skill("plot_umap")
        assert len(results) == 1
        assert results[0].role_id == "viz"

    def test_find_for_skill_sorted(self):
        reg = RoleRegistry()
        reg.register(RoleDefinition(role_id="a", name="A", allowed_skills=["s"], priority=100))
        reg.register(RoleDefinition(role_id="b", name="B", allowed_skills=["s"], priority=10))

        results = reg.find_for_skill("s")
        assert results[0].role_id == "b"  # lower priority = higher score

    def test_load_role_yaml(self, tmp_path):
        reg = RoleRegistry()
        path = tmp_path / "test_role.yaml"
        path.write_text("""
role_id: tester
name: Test Role
allowed_skills:
  - scanpy_qc
""")
        role = reg.load_role(path)
        assert role.role_id == "tester"
        assert "scanpy_qc" in role.allowed_skills

    def test_load_role_json(self, tmp_path):
        reg = RoleRegistry()
        path = tmp_path / "test_role.json"
        import json
        path.write_text(json.dumps({"role_id": "j", "name": "J"}))
        role = reg.load_role(path)
        assert role.role_id == "j"

    def test_load_all(self, tmp_path):
        reg = RoleRegistry()
        (tmp_path / "a.yaml").write_text("role_id: a\nname: A")
        (tmp_path / "b.yaml").write_text("role_id: b\nname: B")
        count = reg.load_all(tmp_path)
        assert count == 2
        assert reg.get("a") is not None
        assert reg.get("b") is not None


class TestDynamicAgent:

    def test_init(self):
        role = RoleDefinition(role_id="viz", name="Viz", agent_type="viz", allowed_skills=["plot_umap"])
        agent = DynamicAgent(role=role)
        assert agent.name == "Viz"
        assert agent.can_handle("plot_umap") is True
        assert agent.can_handle("scanpy_qc") is False

    @pytest.mark.asyncio
    async def test_run_with_skill(self):
        role = RoleDefinition(role_id="bio", name="Bio", allowed_skills=["scanpy_qc"])
        agent = DynamicAgent(role=role, skill_executor=FakeSkillExecutor())
        task = FakeTask("qc_task", skills=["scanpy_qc"])
        result = await agent.run(task, {})
        assert result["role_id"] == "bio"
        assert result["skill"] == "scanpy_qc"
        assert result["result"]["skill_id"] == "scanpy_qc"

    @pytest.mark.asyncio
    async def test_run_unauthorized_skill(self):
        role = RoleDefinition(role_id="bio", name="Bio", allowed_skills=["scanpy_qc"])
        agent = DynamicAgent(role=role, skill_executor=FakeSkillExecutor())
        task = FakeTask("viz_task", skills=["plot_umap"])
        result = await agent.run(task, {})
        assert "error" in result
        assert "cannot handle" in result["error"]

    @pytest.mark.asyncio
    async def test_review_disabled(self):
        role = RoleDefinition(role_id="bio", name="Bio")
        agent = DynamicAgent(role=role)
        result = await agent.review(None, {})
        assert result["approved"] is True
        assert result["reason"] == "review_not_enabled"

    @pytest.mark.asyncio
    async def test_review_enabled(self):
        role = RoleDefinition(role_id="qa", name="QA", permissions=RolePermissions(can_review=True))
        agent = DynamicAgent(role=role)
        result = await agent.review(None, {})
        assert result["approved"] is True
        assert result["role_id"] == "qa"

    def test_get_system_prompt(self):
        role = RoleDefinition(role_id="r", name="R", system_prompt="Hello {name}")
        agent = DynamicAgent(role=role)
        assert agent.get_system_prompt({"name": "world"}) == "Hello world"

    def test_get_system_prompt_no_substitution(self):
        role = RoleDefinition(role_id="r", name="R", system_prompt="Static prompt")
        agent = DynamicAgent(role=role)
        assert agent.get_system_prompt() == "Static prompt"


class TestAgentCore:

    def test_init_analyst(self, agent_core):
        analyst = agent_core.init_analyst()
        assert analyst is not None
        assert analyst.role.role_id == "analyst"
        assert analyst.role.permissions.can_spawn_specialist is True

    def test_init_analyst_caches(self, agent_core):
        a1 = agent_core.init_analyst()
        a2 = agent_core.init_analyst()
        assert a1 is a2

    def test_spawn_specialist(self, agent_core):
        agent_core.init_analyst()
        viz = agent_core.spawn_specialist("viz")
        assert viz.role.role_id == "viz"
        assert viz.name.startswith("Viz")
        assert "Viz" in agent_core.list_specialists()[0].name

    def test_spawn_specialist_unknown_role(self, agent_core):
        with pytest.raises(ValueError, match="not found"):
            agent_core.spawn_specialist("missing")

    def test_dismiss_specialist(self, agent_core):
        agent_core.init_analyst()
        viz = agent_core.spawn_specialist("viz")
        assert agent_core.dismiss_specialist(viz.name) is True
        assert agent_core.dismiss_specialist(viz.name) is False

    def test_resolve_agent_explicit_assignment(self, agent_core):
        agent_core.init_analyst()
        task = FakeTask("t", skills=["plot_umap"], agent_assignment=AgentType.BIOINFO)
        # Register a fake agent with that type
        class FakeAgent(BaseAgent):
            agent_type = AgentType.BIOINFO
            async def run(self, task, context):
                return {}
        agent_core.agent_registry.register(FakeAgent())
        resolved = agent_core.resolve_agent_for_task(task)
        assert resolved.agent_type == AgentType.BIOINFO

    def test_resolve_agent_analyst_fallback(self, agent_core):
        agent_core.init_analyst()
        task = FakeTask("t", skills=["unknown_skill"])
        # Analyst allows "*"
        resolved = agent_core.resolve_agent_for_task(task)
        assert resolved is not None
        assert resolved.role.role_id == "analyst"

    def test_resolve_agent_spawn_specialist(self, agent_core):
        agent_core.init_analyst()
        task = FakeTask("t", skills=["plot_umap"])
        # Analyst does NOT have plot_umap in its allowed_skills?
        # Actually analyst has "*" so it matches everything.
        # Let's override analyst role to not have wildcard for this test.
        agent_core._analyst.role.allowed_skills = ["scanpy_qc"]
        resolved = agent_core.resolve_agent_for_task(task)
        assert resolved is not None
        assert resolved.role.role_id == "viz"

    def test_resolve_agent_no_match(self, agent_core):
        agent_core.init_analyst()
        # Block all skills for analyst and no matching specialist
        agent_core._analyst.role.blocked_skills = ["*"]
        task = FakeTask("t", skills=["unknown_xyz"])
        assert agent_core.resolve_agent_for_task(task) is None

    def test_list_specialists(self, agent_core):
        agent_core.init_analyst()
        assert len(agent_core.list_specialists()) == 0
        agent_core.spawn_specialist("viz")
        assert len(agent_core.list_specialists()) == 1

    def test_reset(self, agent_core):
        agent_core.init_analyst()
        agent_core.spawn_specialist("viz")
        agent_core.reset()
        assert len(agent_core.list_specialists()) == 0
        assert agent_core.get_analyst() is not None


class TestIntegration:

    def test_role_yaml_loading(self, tmp_path):
        reg = RoleRegistry()
        yaml_content = """
role_id: integrator
name: Integration Tester
description: Tests YAML loading
agent_type: bioinfo
allowed_skills:
  - scanpy_qc
  - scanpy_pca
allowed_skill_categories:
  - preprocessing
system_prompt: "You are an integration test role."
permissions:
  can_execute: true
  can_review: false
  can_spawn_specialist: false
priority: 25
tags:
  - test
  - integration
"""
        path = tmp_path / "integrator.yaml"
        path.write_text(yaml_content)
        role = reg.load_role(path)
        assert role.role_id == "integrator"
        assert role.priority == 25
        assert "preprocessing" in role.allowed_skill_categories
        assert role.permissions.can_execute is True
        assert role.tags == ["test", "integration"]

    @pytest.mark.asyncio
    async def test_full_pipeline(self, agent_core):
        agent_core.init_analyst()

        # Analyst handles a task
        task = FakeTask("plan", skills=["scanpy_qc"])
        analyst = agent_core.resolve_agent_for_task(task)
        result = await analyst.run(task, {})
        assert result["role_id"] == "analyst"

        # Specialist spawned for viz
        viz_task = FakeTask("plot", skills=["plot_umap"])
        # Block analyst from handling plot tasks
        agent_core._analyst.role.allowed_skills = ["scanpy_qc"]
        viz_agent = agent_core.resolve_agent_for_task(viz_task)
        assert viz_agent.role.role_id == "viz"
        viz_result = await viz_agent.run(viz_task, {})
        assert viz_result["skill"] == "plot_umap"
