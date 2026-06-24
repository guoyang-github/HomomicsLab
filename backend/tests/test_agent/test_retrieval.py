"""Tests for SkillRetriever and retrieval-augmented planning context."""

import pytest

from homomics_lab.agent.retrieval import RetrievedSkill, RetrievalContext, SkillRetriever
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import EdgeStatus, EdgeType, SkillDAG


@pytest.fixture
def skill_registry():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            description="Quality control for single-cell data",
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_normalize",
            name="scanpy_normalize",
            version="1.0",
            category="single_cell",
            description="Normalize single-cell counts",
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_pca",
            name="scanpy_pca",
            version="1.0",
            category="single_cell",
            description="Run PCA on single-cell data",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


class TestSkillRetriever:
    @pytest.mark.asyncio
    async def test_retrieve_without_dag(self, skill_registry):
        retriever = SkillRetriever(skill_registry=skill_registry)
        context = await retriever.retrieve("quality control single cell", "single_cell_analysis")

        assert isinstance(context, RetrievalContext)
        assert context.intent_type == "single_cell_analysis"
        assert any(s.skill.id == "scanpy_qc" for s in context.skills)

    @pytest.mark.asyncio
    async def test_retrieve_with_dag(self, skill_registry, tmp_path):
        dag = SkillDAG(registry=skill_registry, db_path=tmp_path / "dag.db")
        dag.propose_edge("scanpy_qc", "scanpy_normalize", EdgeType.FOLLOWED_BY)
        edge = dag.edges["scanpy_qc_followed_by_scanpy_normalize"]
        edge.status = EdgeStatus.CONFIRMED
        edge.confidence = 0.9

        retriever = SkillRetriever(skill_registry=skill_registry, skill_dag=dag)
        context = await retriever.retrieve("quality control", "single_cell_analysis")

        qc_retrieved = next((s for s in context.skills if s.skill.id == "scanpy_qc"), None)
        assert qc_retrieved is not None
        assert "scanpy_normalize" in qc_retrieved.followed_by

    @pytest.mark.asyncio
    async def test_retrieve_prompt_context(self, skill_registry):
        retriever = SkillRetriever(skill_registry=skill_registry)
        context = await retriever.retrieve("quality control", "single_cell_analysis")
        prompt_context = context.to_prompt_context(max_skills=2)

        assert prompt_context["query"] == "quality control"
        assert prompt_context["intent_type"] == "single_cell_analysis"
        assert len(prompt_context["skills"]) <= 2
        assert "id" in prompt_context["skills"][0]
        assert "score" in prompt_context["skills"][0]

    def test_retrieved_skill_dataclass(self):
        skill = SkillDefinition(
            id="test",
            name="test",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(),
        )
        rs = RetrievedSkill(skill=skill, semantic_score=0.9, graph_boost=0.1)
        assert rs.skill.id == "test"
