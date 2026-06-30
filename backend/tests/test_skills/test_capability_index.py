"""Tests for the unified CapabilityIndex."""

import pytest
import pytest_asyncio

from homomics_lab.config import Settings
from homomics_lab.context.feedback_store import FeedbackOutcome
from homomics_lab.knowledge.cbkb import ExperimentNode
from homomics_lab.skills.capability_index import CapabilityCandidate, CapabilityIndex, CapabilityType
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.tools.models import ToolDefinition

CACHED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    from homomics_lab.context.graph.factory import reset_graph_backend
    from homomics_lab.context.vector_store.factory import reset_vector_store
    from homomics_lab.embeddings.factory import reset_embedding_provider

    reset_embedding_provider()
    reset_vector_store()
    reset_graph_backend()
    return Settings(
        data_dir=tmp_path,
        embedding_provider="sentence_transformers",
        embedding_model=CACHED_MODEL,
        vector_store_backend="sqlite-vec",
        graph_backend="networkx",
    )


@pytest_asyncio.fixture
async def index(settings):
    idx = CapabilityIndex(settings=settings)
    yield idx
    await idx.close()


@pytest.mark.asyncio
async def test_index_and_search_skill(index):
    skill = SkillDefinition(
        id="bio-single-cell-qc",
        name="Single-cell QC",
        version="1.0.0",
        category="single-cell",
        description="Filter low-quality cells and genes from single-cell RNA-seq data.",
        metadata={"tags": ["scanpy", "qc"]},
    )
    await index.index_skill(skill)

    results = await index.search("filter low quality cells", top_k=3)
    assert any(r.id == "bio-single-cell-qc" for r in results)
    assert all(isinstance(r, CapabilityCandidate) for r in results)


@pytest.mark.asyncio
async def test_index_and_search_tool(index):
    tool = ToolDefinition(
        name="pubmed_search",
        description="Search PubMed for biomedical literature.",
        input_schema={"type": "object"},
    )
    await index.index_tool(tool)

    results = await index.search("PubMed literature", top_k=3, item_types=[CapabilityType.TOOL])
    assert any(r.id == "pubmed_search" for r in results)


@pytest.mark.asyncio
async def test_search_filters_by_item_type(index):
    skill = SkillDefinition(
        id="plot-umap",
        name="UMAP plot",
        version="1.0.0",
        category="viz",
        description="Visualize single-cell clusters with UMAP.",
    )
    tool = ToolDefinition(
        name="file_read",
        description="Read a file from disk.",
        input_schema={"type": "object"},
    )
    await index.index_skill(skill)
    await index.index_tool(tool)

    skill_results = await index.search("read file", top_k=5, item_types=[CapabilityType.SKILL])
    tool_results = await index.search("read file", top_k=5, item_types=[CapabilityType.TOOL])
    assert all(r.type == CapabilityType.SKILL for r in skill_results)
    assert all(r.type == CapabilityType.TOOL for r in tool_results)


@pytest.mark.asyncio
async def test_index_experiment_creates_graph_edges(index, settings):
    skill = SkillDefinition(
        id="scanpy-cluster",
        name="Scanpy clustering",
        version="1.0.0",
        category="single-cell",
        description="Cluster single-cell data with Leiden algorithm.",
    )
    await index.index_skill(skill)

    experiment = ExperimentNode(
        bundle_id="exp-001",
        project_id="proj-1",
        created_at="2024-01-01T00:00:00Z",
        skills_used=["scanpy-cluster"],
        phases=["qc", "cluster"],
        summary="PBMC clustering experiment",
    )
    await index.index_experiment(experiment)

    neighbors = await index.get_neighbors(
        "exp-001", CapabilityType.EXPERIMENT, edge_types=["USES_SKILL"]
    )
    assert any(r.id == "scanpy-cluster" for r in neighbors)


@pytest.mark.asyncio
async def test_feedback_reranks_capabilities(index):
    skill_good = SkillDefinition(
        id="good-skill",
        name="Good skill",
        version="1.0.0",
        category="test",
        description="A reliable skill for testing.",
    )
    skill_bad = SkillDefinition(
        id="bad-skill",
        name="Bad skill",
        version="1.0.0",
        category="test",
        description="A less reliable skill for testing.",
    )
    await index.index_skill(skill_good)
    await index.index_skill(skill_bad)

    # Without feedback both should score similarly; record divergent feedback.
    await index.add_feedback("good-skill", CapabilityType.SKILL, FeedbackOutcome.SUCCESS)
    await index.add_feedback("good-skill", CapabilityType.SKILL, FeedbackOutcome.SUCCESS)
    await index.add_feedback("bad-skill", CapabilityType.SKILL, FeedbackOutcome.FAILURE)

    results = await index.search("reliable skill for testing", top_k=5)
    good = next(r for r in results if r.id == "good-skill")
    bad = next(r for r in results if r.id == "bad-skill")
    assert good.score > bad.score
