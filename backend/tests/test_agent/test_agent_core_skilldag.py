"""Tests for AgentCore + SkillDAG integration."""

import pytest

from homomics_lab.agent.core import AgentCore, DynamicAgent, RoleDefinition
from homomics_lab.agent.agent_registry import AgentRegistry


class FakeSkillDAG:
    """Minimal mock of SkillDAG for integration testing."""

    def __init__(self):
        self.edges = []

    def add_edge(self, from_skill, to_skill, edge_type="followed_by", confidence=0.8):
        self.edges.append({
            "from_skill": from_skill,
            "to_skill": to_skill,
            "edge_type": edge_type,
            "confidence": confidence,
        })

    def get_followed_by(self, skill_id, min_confidence=0.6):
        return [
            (e["to_skill"], e["confidence"])
            for e in self.edges
            if e["from_skill"] == skill_id
            and e["edge_type"] == "followed_by"
            and e["confidence"] >= min_confidence
        ]

    def get_conflicts(self, skill_id):
        return [
            e["to_skill"]
            for e in self.edges
            if e["from_skill"] == skill_id and e["edge_type"] == "conflicts_with"
        ]

    def validate_sequence(self, skill_sequence):
        class Result:
            def __init__(self, valid, errors=None, warnings=None):
                self.valid = valid
                self.errors = errors or []
                self.warnings = warnings or []
        seen = set()
        errors = []
        for i, skill in enumerate(skill_sequence):
            for e in self.edges:
                if e["edge_type"] == "conflicts_with":
                    if e["from_skill"] == skill and e["to_skill"] in seen:
                        errors.append(f"Conflict: {skill} conflicts with {e['to_skill']}")
                    if e["to_skill"] == skill and e["from_skill"] in seen:
                        errors.append(f"Conflict: {skill} conflicts with {e['from_skill']}")
            seen.add(skill)
        return Result(valid=len(errors) == 0, errors=errors)


class FakeTask:
    def __init__(self, name, skills=None, agent_assignment=None):
        self.name = name
        self.skills_required = skills or []
        self.agent_assignment = agent_assignment
        self.parameters = {}


@pytest.fixture
def agent_core_with_dag():
    dag = FakeSkillDAG()
    dag.add_edge("scanpy_qc", "scanpy_pca", "followed_by", 0.9)
    dag.add_edge("scanpy_pca", "scanpy_cluster", "followed_by", 0.85)
    dag.add_edge("scanpy_qc", "scanpy_de", "conflicts_with", 1.0)

    core = AgentCore(
        agent_registry=AgentRegistry(),
        skill_dag=dag,
    )
    core.role_registry.register(RoleDefinition(
        role_id="analyst",
        name="Analyst",
        agent_type="bioinfo",
        allowed_skills=["*"],
        priority=10,
    ))
    core.role_registry.register(RoleDefinition(
        role_id="qc",
        name="QC",
        agent_type="bioinfo",
        allowed_skills=["scanpy_qc", "scanpy_pca"],
        priority=20,
    ))
    return core


class TestAgentCoreSkillDAG:

    def test_recommend_next_skills(self, agent_core_with_dag):
        recs = agent_core_with_dag.recommend_next_skills("scanpy_qc")
        assert len(recs) == 1
        assert recs[0][0] == "scanpy_pca"
        assert recs[0][1] == 0.9

    def test_recommend_empty_when_no_dag(self):
        core = AgentCore()
        assert core.recommend_next_skills("scanpy_qc") == []

    def test_recommend_respects_min_confidence(self, agent_core_with_dag):
        recs = agent_core_with_dag.recommend_next_skills("scanpy_qc", min_confidence=0.95)
        assert len(recs) == 0

    def test_resolve_validates_sequence_no_conflict(self, agent_core_with_dag):
        core = agent_core_with_dag
        core.init_analyst()
        task = FakeTask("pca", skills=["scanpy_pca"])
        agent = core.resolve_agent_for_task(task, executed_skills=["scanpy_qc"])
        assert agent is not None

    def test_resolve_detects_conflict(self, agent_core_with_dag):
        core = agent_core_with_dag
        core.init_analyst()
        task = FakeTask("de", skills=["scanpy_de"])
        with pytest.raises(ValueError, match="Skill sequence invalid"):
            core.resolve_agent_for_task(task, executed_skills=["scanpy_qc"])

    def test_dynamic_agent_recommendations(self, agent_core_with_dag):
        core = agent_core_with_dag
        core.init_analyst()
        agent = core.spawn_specialist("qc")
        recs = agent.get_skill_recommendations(core.skill_dag)
        # QC role has scanpy_qc and scanpy_pca
        # From scanpy_qc → scanpy_pca is recommended
        assert any(r["to_skill"] == "scanpy_pca" for r in recs)

    def test_dynamic_agent_no_recommendations_without_dag(self):
        role = RoleDefinition(role_id="r", name="R", allowed_skills=["scanpy_qc"])
        agent = DynamicAgent(role=role)
        assert agent.get_skill_recommendations(None) == []
