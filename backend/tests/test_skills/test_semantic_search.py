import pytest
from homomics_lab.skills.semantic_search import SkillSemanticSearch
from homomics_lab.skills.models import SkillDefinition


class TestSkillSemanticSearch:
    def test_search_by_description(self):
        search = SkillSemanticSearch()
        search.add(SkillDefinition(
            id="cluster", name="Cluster Cells", version="1.0", category="single-cell",
            description="Cluster single cells using Leiden algorithm",
            metadata={"keywords": ["clustering", "leiden", "single-cell"]},
        ))
        search.add(SkillDefinition(
            id="qc", name="Quality Control", version="1.0", category="single-cell",
            description="Filter low quality cells and genes",
            metadata={"keywords": ["qc", "filtering"]},
        ))

        results = search.search("group cells into clusters")
        assert len(results) > 0
        assert results[0][0].id == "cluster"

    def test_search_by_tool_name(self):
        search = SkillSemanticSearch()
        search.add(SkillDefinition(
            id="seurat-cluster", name="Seurat Clustering", version="1.0", category="single-cell",
            description="Cluster with Seurat FindClusters",
            metadata={"primary_tool": "Seurat", "supported_tools": ["Seurat"]},
        ))

        results = search.search("Seurat")
        assert len(results) > 0
        assert results[0][0].id == "seurat-cluster"

    def test_search_returns_scores(self):
        search = SkillSemanticSearch()
        search.add(SkillDefinition(
            id="a", name="A", version="1.0", category="test",
            description="Something about clustering",
            metadata={"keywords": []},
        ))

        results = search.search("clustering")
        assert len(results) == 1
        assert 0 < results[0][1] <= 1.0

    def test_empty_search(self):
        search = SkillSemanticSearch()
        results = search.search("anything")
        assert results == []

    def test_search_ids(self):
        search = SkillSemanticSearch()
        search.add(SkillDefinition(
            id="de", name="DE Analysis", version="1.0", category="single-cell",
            description="Find differentially expressed genes",
            metadata={"keywords": ["differential", "expression"]},
        ))

        ids = search.search_ids("find marker genes")
        assert ids == ["de"]
