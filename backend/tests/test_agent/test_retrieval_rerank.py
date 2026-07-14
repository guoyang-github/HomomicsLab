"""Tests for the BM25 skill reranker and the thresholded fallback paths.

Covers:
  - SkillReranker BM25 ordering and min_score filtering (Fix B)
  - SkillRetriever._retrieve_skills applying rerank + threshold (Fix B)
  - PlanEngine._select_skill_for_phase no longer force-matching unrelated
    phase names to arbitrary skills (Fix A)
"""

import pytest

from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.agent.retrieval import RetrievedSkill, SkillRetriever
from homomics_lab.agent.retrieval_rerank import SkillReranker
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


def _make_skill(skill_id: str, description: str) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        version="1.0",
        category="single_cell",
        description=description,
    )


SCANPY_SKILLS = [
    _make_skill("scanpy_qc", "Quality control of droplet count matrices"),
    _make_skill("scanpy_normalize", "Library-size normalization and log transform"),
    _make_skill("scanpy_pca", "Principal component embedding of expression"),
    _make_skill("scanpy_cluster", "Leiden community detection on neighbour graph"),
]


@pytest.fixture
def scanpy_registry():
    registry = SkillRegistry()
    for skill in SCANPY_SKILLS:
        registry.register(skill)
    return registry


def _candidates(score: float = 0.0):
    return [RetrievedSkill(skill=s, semantic_score=score) for s in SCANPY_SKILLS]


class TestSkillReranker:
    def test_bm25_ranks_relevant_skill_first(self):
        reranker = SkillReranker()
        ranked = reranker.rerank(
            "leiden clustering", _candidates(), corpus=SCANPY_SKILLS
        )
        assert ranked
        assert ranked[0].skill.id == "scanpy_cluster"
        # Composite score is written to semantic_score; raw score preserved.
        assert ranked[0].semantic_score >= reranker.min_score
        assert ranked[0].raw_semantic_score == 0.0

    def test_meaningless_query_drops_all_candidates(self):
        reranker = SkillReranker()
        ranked = reranker.rerank("x_alpha zzz", _candidates(), corpus=SCANPY_SKILLS)
        assert ranked == []

    def test_min_score_is_configurable(self):
        # With the floor removed, even a zero-overlap query keeps candidates
        # (they only carry their upstream semantic score).
        reranker = SkillReranker(min_score=0.0)
        ranked = reranker.rerank(
            "x_alpha zzz", _candidates(score=0.02), corpus=SCANPY_SKILLS
        )
        assert ranked
        assert all(rs.semantic_score < 0.1 for rs in ranked)

    def test_top_k_applies_after_thresholding(self):
        reranker = SkillReranker()
        ranked = reranker.rerank(
            "single cell analysis", _candidates(), top_k=2, corpus=SCANPY_SKILLS
        )
        assert len(ranked) <= 2
        assert all(rs.semantic_score >= reranker.min_score for rs in ranked)

    def test_graph_boost_contributes_to_composite(self):
        reranker = SkillReranker(min_score=0.0)
        plain = [RetrievedSkill(skill=SCANPY_SKILLS[3], semantic_score=0.0)]
        boosted = [RetrievedSkill(skill=SCANPY_SKILLS[3], semantic_score=0.0, graph_boost=0.5)]
        plain_score = reranker.rerank("leiden", plain, corpus=SCANPY_SKILLS)[0].semantic_score
        boosted_score = reranker.rerank("leiden", boosted, corpus=SCANPY_SKILLS)[0].semantic_score
        assert boosted_score > plain_score


class TestRetrieverRerankIntegration:
    def test_meaningless_query_returns_nothing(self, scanpy_registry):
        retriever = SkillRetriever(skill_registry=scanpy_registry, skill_dag=None)
        skills = retriever._retrieve_skills("x_alpha zzz", top_k=5, include_graph=False)
        assert skills == []

    def test_relevant_query_hits_expected_skill_first(self, scanpy_registry):
        retriever = SkillRetriever(skill_registry=scanpy_registry, skill_dag=None)
        skills = retriever._retrieve_skills("leiden clustering", top_k=5, include_graph=False)
        assert skills
        assert skills[0].skill.id == "scanpy_cluster"
        assert skills[0].semantic_score >= retriever.reranker.min_score

    def test_rerank_min_score_constructor_override(self, scanpy_registry):
        retriever = SkillRetriever(
            skill_registry=scanpy_registry, skill_dag=None, rerank_min_score=0.95
        )
        skills = retriever._retrieve_skills("leiden clustering", top_k=5, include_graph=False)
        assert skills == []


class TestPlanEngineFallbackThreshold:
    """Fix A: the phase-level registry fallback must respect a similarity floor."""

    def test_unrelated_phase_stays_unmatched(self, scanpy_registry):
        engine = PlanEngine(skill_registry=scanpy_registry, skill_dag=None)
        for phase_type in ("paga_trajectory", "x_alpha"):
            phase = Phase(phase_type=phase_type, description="")
            selected = engine._select_skill_for_phase(phase, DataState(), retrieval_context=None)
            assert selected is None, f"{phase_type} was force-matched to {selected.id if selected else None}"

    def test_relevant_phase_still_matches(self, scanpy_registry):
        engine = PlanEngine(skill_registry=scanpy_registry, skill_dag=None)
        phase = Phase(
            phase_type="normalization",
            description="Library-size normalization and log transform",
        )
        selected = engine._select_skill_for_phase(phase, DataState(), retrieval_context=None)
        assert selected is not None
        assert selected.id == "scanpy_normalize"

    def test_threshold_is_configurable(self, scanpy_registry):
        # An unattainably high floor suppresses even a genuine match.
        engine = PlanEngine(
            skill_registry=scanpy_registry, skill_dag=None, fallback_min_similarity=0.99
        )
        phase = Phase(
            phase_type="normalization",
            description="Library-size normalization and log transform",
        )
        selected = engine._select_skill_for_phase(phase, DataState(), retrieval_context=None)
        assert selected is None
