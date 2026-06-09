"""Tests for sentence-transformers based semantic search."""

import pytest

from homomics_lab.skills.models import SkillDefinition, SkillRuntime
from homomics_lab.skills.semantic_search_v2 import SemanticSearchEngine


@pytest.fixture
def sample_skills():
    return [
        SkillDefinition(
            id="scanpy_qc",
            name="Quality Control",
            version="1.0",
            description="Perform quality control filtering on single cell RNA-seq data",
            category="single-cell",
            runtime=SkillRuntime(type="python", dependencies=["scanpy"]),
            metadata={
                "keywords": ["qc", "filtering", "single-cell"],
                "supported_tools": ["scanpy", "anndata"],
                "primary_tool": "scanpy",
            },
        ),
        SkillDefinition(
            id="seurat_cluster",
            name="Seurat Clustering",
            version="1.0",
            description="Cluster cells using Seurat Louvain algorithm",
            category="single-cell",
            runtime=SkillRuntime(type="r", dependencies=["Seurat"]),
            metadata={
                "keywords": ["clustering", "louvain", "single-cell"],
                "supported_tools": ["Seurat"],
                "primary_tool": "Seurat",
            },
        ),
        SkillDefinition(
            id="spatial_deconv",
            name="Spatial Deconvolution",
            version="1.0",
            description="Deconvolve spatial transcriptomics spots",
            category="spatial-transcriptomics",
            runtime=SkillRuntime(type="python", dependencies=["squidpy"]),
            metadata={
                "keywords": ["spatial", "deconvolution", "transcriptomics"],
                "supported_tools": ["squidpy", "scanpy"],
                "primary_tool": "squidpy",
            },
        ),
    ]


class TestSemanticSearchEngine:
    def test_init(self):
        engine = SemanticSearchEngine()
        assert engine._model_name == "all-MiniLM-L6-v2"
        assert engine._model is None

    def test_init_custom_model(self):
        engine = SemanticSearchEngine(model_name="custom-model")
        assert engine._model_name == "custom-model"

    def test_add_and_search(self, sample_skills):
        engine = SemanticSearchEngine()
        for skill in sample_skills:
            engine.add(skill)

        # Search for clustering-related query
        results = engine.search("cluster cells", top_k=3)
        assert len(results) > 0
        # Seurat clustering should be top result
        assert results[0][0].id == "seurat_cluster"
        assert results[0][1] > 0.5  # High similarity

    def test_search_spatial(self, sample_skills):
        engine = SemanticSearchEngine()
        for skill in sample_skills:
            engine.add(skill)

        results = engine.search("spatial transcriptomics analysis", top_k=3)
        assert len(results) > 0
        # Spatial deconvolution should be top result
        assert results[0][0].id == "spatial_deconv"

    def test_search_qc(self, sample_skills):
        engine = SemanticSearchEngine()
        for skill in sample_skills:
            engine.add(skill)

        results = engine.search("filter low quality cells", top_k=3)
        assert len(results) > 0
        # QC skill should be top result
        assert results[0][0].id == "scanpy_qc"

    def test_search_ids(self, sample_skills):
        engine = SemanticSearchEngine()
        for skill in sample_skills:
            engine.add(skill)

        ids = engine.search_ids("clustering", top_k=2)
        assert "seurat_cluster" in ids

    def test_remove(self, sample_skills):
        engine = SemanticSearchEngine()
        for skill in sample_skills:
            engine.add(skill)

        engine.remove("seurat_cluster")
        results = engine.search("cluster cells", top_k=3)
        ids = [r[0].id for r in results]
        assert "seurat_cluster" not in ids

    def test_search_empty_index(self):
        engine = SemanticSearchEngine()
        results = engine.search("anything")
        assert results == []

    def test_search_no_results(self, sample_skills):
        engine = SemanticSearchEngine()
        for skill in sample_skills:
            engine.add(skill)

        # Search for something completely unrelated
        results = engine.search("quantum physics", top_k=3)
        assert len(results) == 0  # Should return nothing due to threshold

    def test_lazy_model_loading(self, sample_skills):
        engine = SemanticSearchEngine()
        assert engine._model is None  # Not loaded yet

        engine.add(sample_skills[0])
        engine.search("test")  # This triggers lazy loading
        assert engine._model is not None
