"""Tests for the extended SkillRetriever (tools + data sources)."""


import pytest

from homomics_lab.agent.retrieval import SkillRetriever
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_retrieve_tools_by_description():
    registry = SkillRegistry()
    tool_registry = ToolRegistry()
    tool_registry.register_builtin(
        name="pubmed_search",
        description="Search PubMed for biomedical literature",
        handler=lambda query: query,
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        risk_level="low",
    )
    tool_registry.register_builtin(
        name="shell_exec",
        description="Execute a shell command",
        handler=lambda command: command,
        risk_level="high",
    )

    retriever = SkillRetriever(registry, tool_registry=tool_registry)
    ctx = await retriever.retrieve("find papers about scRNA-seq", "literature_review")

    assert any(t.name == "pubmed_search" for t in ctx.tools)
    assert not any(t.name == "shell_exec" for t in ctx.tools)


@pytest.mark.asyncio
async def test_retrieve_data_sources():
    registry = SkillRegistry()
    data_sources = [
        {"id": "gtex", "path": "data/gtex.csv", "format": "csv", "description": "GTEx gene expression"},
        {"id": "pbmc3k", "path": "data/pbmc3k.h5ad", "format": "h5ad", "description": "PBMC demo"},
    ]

    retriever = SkillRetriever(registry, data_sources=data_sources)
    ctx = await retriever.retrieve("PBMC single cell analysis", "single_cell_analysis")

    assert any(d.id == "pbmc3k" for d in ctx.data_sources)
    assert not any(d.id == "gtex" for d in ctx.data_sources)


@pytest.mark.asyncio
async def test_prompt_context_includes_tools_and_data_sources():
    registry = SkillRegistry()
    tool_registry = ToolRegistry()
    tool_registry.register_builtin(
        name="pubmed_search",
        description="Search PubMed",
        handler=lambda query: query,
    )
    data_sources = [
        {"id": "pbmc3k", "path": "data/pbmc3k.h5ad", "format": "h5ad", "description": "PBMC demo"},
    ]

    retriever = SkillRetriever(registry, tool_registry=tool_registry, data_sources=data_sources)
    ctx = await retriever.retrieve("single cell PBMC paper analysis", "single_cell_analysis")
    prompt_ctx = ctx.to_prompt_context()

    assert any(t["name"] == "pubmed_search" for t in prompt_ctx["tools"])
    assert any(d["id"] == "pbmc3k" for d in prompt_ctx["data_sources"])


@pytest.mark.asyncio
async def test_override_data_sources_per_retrieve():
    registry = SkillRegistry()
    default_sources = [
        {"id": "default", "path": "data/default.csv", "format": "csv", "description": "Default"},
    ]
    override_sources = [
        {"id": "override", "path": "data/override.csv", "format": "csv", "description": "Override"},
    ]

    retriever = SkillRetriever(registry, data_sources=default_sources)
    ctx = await retriever.retrieve("override analysis", "test", data_sources=override_sources)

    assert any(d.id == "override" for d in ctx.data_sources)
    assert not any(d.id == "default" for d in ctx.data_sources)
