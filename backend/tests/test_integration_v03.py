"""Integration tests for v0.3.0 architecture.

Covers cross-module workflows:
  - AgentCore + Orchestrator + DynamicAgent
  - WorkspaceManager + VersionLocker + SkillRuntime
  - PlanEngine + InterpretationEngine
"""

import pytest

from homomics_lab.agent.core import AgentCore, RoleDefinition, RoleRegistry
from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.interpretation import InterpretationEngine
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.models import DataState
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.workspace.manager import WorkspaceManager
from homomics_lab.models.common import TaskStatus
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


class FakeTask:
    def __init__(self, name, skills=None, agent_assignment=None, parameters=None):
        self.name = name
        self.skills_required = skills or []
        self.agent_assignment = agent_assignment
        self.parameters = parameters or {}
        self.status = TaskStatus.PENDING
        self.dependencies = []
        self.retry_policy = type("RP", (), {"max_attempts": 1, "backoff_seconds": 0})()
        self.attempt_count = 0
        self.error_message = None
        self.result = None


class FakeSkillExecutor:
    def __init__(self, outputs=None):
        self.outputs = outputs or {}

    async def execute(self, skill_id, params):
        return self.outputs.get(skill_id, {"success": True, "output": f"ran {skill_id}"})


@pytest.fixture
def core_with_roles():
    reg = RoleRegistry()
    reg.register(RoleDefinition(
        role_id="analyst",
        name="Analyst",
        agent_type="bioinfo",
        allowed_skills=["*"],
        permissions={"can_spawn_specialist": True},
        priority=10,
    ))
    reg.register(RoleDefinition(
        role_id="qc_specialist",
        name="QC",
        agent_type="bioinfo",
        allowed_skills=["scanpy_qc", "scanpy_filter"],
        priority=20,
    ))
    reg.register(RoleDefinition(
        role_id="viz_specialist",
        name="Viz",
        agent_type="viz",
        allowed_skills=["plot_umap", "plot_heatmap"],
        priority=30,
    ))
    return reg


class TestAgentCoreOrchestratorIntegration:

    @pytest.mark.asyncio
    async def test_full_workflow_with_dynamic_agents(self, core_with_roles, tmp_path):
        """Analyst spawns specialists, orchestrator runs task tree end-to-end."""
        executor = FakeSkillExecutor(outputs={
            "scanpy_qc": {"success": True, "cells_remaining": 2500},
            "plot_umap": {"success": True, "figure": "umap.png"},
        })

        core = AgentCore(
            role_registry=core_with_roles,
            agent_registry=AgentRegistry(),
            skill_executor=executor,
        )
        core.init_analyst()

        # Build task tree
        tree = TaskTree([
            TaskNode(
                id="qc",
                name="quality_control",
                description="Run QC",
                skills_required=["scanpy_qc"],
                parameters={},
            ),
            TaskNode(
                id="viz",
                name="visualization",
                description="Plot UMAP",
                skills_required=["plot_umap"],
                parameters={},
                dependencies=["qc"],
            ),
        ])

        # Use orchestrator with AgentCore's registry
        orchestrator = Orchestrator(registry=core.agent_registry)
        results = await orchestrator.run_tree(tree)

        assert "qc" in results
        assert "viz" in results
        assert tree.get_task("qc").status == TaskStatus.COMPLETED
        assert tree.get_task("viz").status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_analyst_routes_to_specialist(self, core_with_roles):
        """Analyst does not handle viz tasks; spawns a viz specialist."""
        executor = FakeSkillExecutor()
        core = AgentCore(
            role_registry=core_with_roles,
            agent_registry=AgentRegistry(),
            skill_executor=executor,
        )
        core.init_analyst()
        # Restrict analyst to non-viz
        core._analyst.role.allowed_skills = ["scanpy_qc"]

        task = FakeTask("viz_task", skills=["plot_umap"])
        agent = core.resolve_agent_for_task(task)

        assert agent is not None
        assert agent.role.role_id == "viz_specialist"

        result = await agent.run(task, {})
        assert result["skill"] == "plot_umap"


class TestWorkspaceVersionLockIntegration:

    def test_workspace_locks_and_verifies(self, tmp_path):
        ws = WorkspaceManager(base_dir=tmp_path, project_id="proj_a")

        class FakeSkill:
            def __init__(self, sid, ver):
                self.id = sid
                self.version = ver
                self.metadata = {}

        class FakeRegistry:
            def list_all(self):
                return [FakeSkill("norm", "1.0.0"), FakeSkill("cluster", "2.0.0")]

            def get(self, sid):
                return next((s for s in self.list_all() if s.id == sid), None)

        lock = ws.lock_versions(FakeRegistry())
        assert lock.skills["norm"] == "1.0.0"
        assert lock.skills["cluster"] == "2.0.0"

        # Modify version
        class FakeRegistryV2:
            def list_all(self):
                return [FakeSkill("norm", "1.1.0"), FakeSkill("cluster", "2.0.0")]

            def get(self, sid):
                return next((s for s in self.list_all() if s.id == sid), None)

        result = ws.verify_versions(FakeRegistryV2())
        assert result.compatible is False
        assert any("1.1.0" in m for m in result.version_mismatches)


class TestPlanEngineAgentCoreIntegration:

    @pytest.mark.asyncio
    async def test_plan_engine_produces_routable_phases(self):
        """PlanEngine output phases should be resolvable by AgentCore."""
        engine = PlanEngine(skill_registry=SkillRegistry())
        intent = UserIntent(
            intent_type="analysis", interaction_mode="execute", target="single_cell", scope="full", data_scale="medium",
        )
        data_state = DataState()
        plan = await engine.plan(intent, data_state)

        core = AgentCore(
            role_registry=RoleRegistry(),
            agent_registry=AgentRegistry(),
        )
        core.role_registry.register(RoleDefinition(
            role_id="analyst",
            name="Analyst",
            agent_type="bioinfo",
            allowed_skills=["*"],
            priority=10,
        ))
        core.init_analyst()

        # Every phase should be resolvable
        for phase in plan.phases:
            if phase.selected_skill:
                task = FakeTask(phase.name, skills=[phase.selected_skill])
                agent = core.resolve_agent_for_task(task)
                assert agent is not None, f"No agent for skill {phase.selected_skill}"


class TestInterpretationEngineIntegration:

    def test_interpretation_detects_anomaly(self):
        engine = InterpretationEngine()
        phase = type("Phase", (), {"phase_type": "qc", "name": "QC"})()
        # 80% filtered (> 50% threshold) should trigger anomaly
        output = {"input_cells": 1000, "output_cells": 100}
        data_state = DataState()

        interpretation = engine.interpret_phase(phase, output, data_state)
        assert interpretation.quality_assessment is not None
        assert interpretation.quality_assessment.has_anomaly() is True
        assert any("filter" in f.lower() for f in interpretation.quality_assessment.flags)

    def test_interpretation_recommends_next_steps(self):
        engine = InterpretationEngine()
        phase = type("Phase", (), {"phase_type": "clustering", "name": "Cluster"})()
        output = {"n_clusters": 8}
        data_state = DataState(has_clustering=True)

        interpretation = engine.interpret_phase(phase, output, data_state)
        assert len(interpretation.recommendations) > 0
        rec = interpretation.recommendations[0]
        assert rec.confidence > 0
