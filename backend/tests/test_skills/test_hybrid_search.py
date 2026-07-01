"""Tests for HybridSkillSearch."""

import pytest

from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.semantic_search_hybrid import HybridSkillSearch


@pytest.fixture
def registry_with_qc_skills():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="Quality control",
            version="1.0",
            category="single-cell",
            description="Filter low-quality cells and genes from single-cell RNA-seq data.",
            metadata={"tags": ["qc", "filter", "quality-control"]},
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_normalize",
            name="Normalize",
            version="1.0",
            category="single-cell",
            description="Normalize count data per cell.",
        )
    )
    return reg


class TestHybridSkillSearch:
    def test_finds_skill_by_synonym(self, registry_with_qc_skills):
        """Dense embeddings should bridge synonyms like 'QC' and 'quality control'."""
        results = registry_with_qc_skills.search("QC")
        ids = [s.id for s in results]
        assert "scanpy_qc" in ids

    def test_finds_skill_by_keyword(self, registry_with_qc_skills):
        """Sparse TF-IDF / keyword search still works for literal tags."""
        results = registry_with_qc_skills.search("filter")
        ids = [s.id for s in results]
        assert "scanpy_qc" in ids

    def test_hybrid_fusion_combines_signals(self):
        """RRF combines sparse and dense rankings."""
        search = HybridSkillSearch()
        search.add(
            SkillDefinition(
                id="a",
                name="Quality control",
                version="1.0",
                category="single-cell",
                description="Filter cells.",
                metadata={"tags": ["qc"]},
            )
        )
        search.add(
            SkillDefinition(
                id="b",
                name="Clustering",
                version="1.0",
                category="single-cell",
                description="Cluster cells.",
            )
        )

        results = search.search("quality control", top_k=5)
        ids = [s.id for s, _ in results]
        assert ids[0] == "a"

    def test_falls_back_to_sparse_when_dense_unavailable(self, monkeypatch):
        """If dense model cannot be loaded, hybrid still returns sparse results."""
        monkeypatch.setattr(
            "homomics_lab.skills.semantic_search_v2.SemanticSearchEngine",
            raise_on_init,
        )
        search = HybridSkillSearch()
        search.add(
            SkillDefinition(
                id="scanpy_qc",
                name="Quality control",
                version="1.0",
                category="single-cell",
                description="Filter cells.",
                metadata={"tags": ["qc"]},
            )
        )
        results = search.search("qc", top_k=5)
        assert any(s.id == "scanpy_qc" for s, _ in results)


def raise_on_init(*args, **kwargs):
    raise RuntimeError("dense unavailable")
