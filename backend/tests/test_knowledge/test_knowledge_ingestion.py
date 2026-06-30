"""Tests for the knowledge ingestion (Extract-Cognify-Load) pipeline."""

import json
from typing import List

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from homomics_lab.config import Settings
from homomics_lab.context.graph.factory import get_graph_backend, reset_graph_backend
from homomics_lab.context.memory_backend import MemoryBackend
from homomics_lab.context.vector_store.factory import get_vector_store, reset_vector_store
from homomics_lab.embeddings.base import EmbeddingProvider
from homomics_lab.knowledge.ingestion import CognifyPipeline, KnowledgeIndex
from homomics_lab.knowledge.ingestion.builder import KnowledgeGraphBuilder
from homomics_lab.knowledge.ingestion.chunker import TextChunker
from homomics_lab.knowledge.ingestion.extractor import LLMEntityRelationExtractor
from homomics_lab.knowledge.ingestion.models import DocumentSource
from homomics_lab.knowledge.ingestion.parser_registry import ParserRegistry
from homomics_lab.knowledge.ingestion.parsers.plaintext import PlainTextParser
from homomics_lab.llm_client import FakeLLMClient


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for tests."""

    def __init__(self, dimension: int = 8):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def is_available(self) -> bool:
        return True

    def encode(self, texts: List[str]) -> List[List[float]]:
        import hashlib

        results = []
        for text in texts:
            h = hashlib.md5(text.encode("utf-8")).digest()
            vec = [((h[i] / 255.0) - 0.5) * 2 for i in range(self._dimension)]
            results.append(vec)
        return results


@pytest.fixture
def settings(tmp_path):
    reset_graph_backend()
    reset_vector_store()
    return Settings(
        data_dir=tmp_path,
        vector_store_backend="sqlite-vec",
        graph_backend="networkx",
    )


@pytest_asyncio.fixture
async def backends(settings):
    graph = get_graph_backend(settings)
    vector_store = get_vector_store(settings)
    memory = MemoryBackend(settings=settings, embedding_provider=FakeEmbeddingProvider())
    yield graph, vector_store, memory
    await memory.close()
    await vector_store.close()
    reset_vector_store()
    await graph.close()
    reset_graph_backend()


def test_parser_registry_selects_plaintext():
    source = DocumentSource.from_text("hello world", filename="note.txt")
    registry = ParserRegistry()
    parser = registry.select(source)
    assert isinstance(parser, PlainTextParser)


@pytest.mark.asyncio
async def test_plaintext_parser(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# Title\n\nParagraph one.\n\nParagraph two.", encoding="utf-8")
    source = DocumentSource.from_file(path)
    parser = PlainTextParser()
    parsed = await parser.parse(source)
    assert "Title" in parsed.text
    assert len(parsed.paragraphs) == 3


def test_chunker_splits_text():
    source = DocumentSource.from_text("p1\n\np2\n\np3", filename="t.txt")
    parsed = PlainTextParser()
    import asyncio

    doc = asyncio.run(parsed.parse(source))
    chunker = TextChunker()
    chunks = chunker.chunk(doc, "doc-1")
    assert len(chunks) >= 3
    assert all(c.document_id == "doc-1" for c in chunks)


@pytest.mark.asyncio
async def test_extractor_parses_json():
    fake_response = json.dumps(
        {
            "entities": [
                {"name": "CRISPR", "type": "method", "description": "Gene editing."}
            ],
            "relations": [
                {"source": "CRISPR", "target": "gene", "relation_type": "edits"}
            ],
        }
    )
    client = FakeLLMClient(response=fake_response)
    extractor = LLMEntityRelationExtractor(llm_client=client)
    fragment = await extractor.extract("CRISPR edits genes.")
    assert any(e.name == "CRISPR" for e in fragment.entities)
    assert any(r.source == "CRISPR" for r in fragment.relations)


@pytest.mark.asyncio
async def test_builder_writes_graph_and_vector(backends, settings):
    graph, vector_store, memory = backends
    builder = KnowledgeGraphBuilder(
        graph_backend=graph,
        vector_store=vector_store,
        memory_backend=memory,
        embedding_provider=FakeEmbeddingProvider(),
    )
    source = DocumentSource.from_text("CRISPR is a gene editing method.", filename="test.txt")
    parsed = PlainTextParser()
    doc = await parsed.parse(source)
    chunker = TextChunker()
    chunks = chunker.chunk(doc, "doc-1")

    from homomics_lab.knowledge.ingestion.models import ExtractedEntity, ExtractedRelation, KnowledgeGraphFragment

    fragment = KnowledgeGraphFragment(
        entities=[ExtractedEntity(name="CRISPR", entity_type="method")],
        relations=[ExtractedRelation(source="CRISPR", target="gene", relation_type="edits")],
    )

    result = await builder.build(
        document_id="doc-1",
        parsed=doc,
        chunks=chunks,
        fragment=fragment,
        summary="Summary",
        project_id="proj-1",
    )

    assert len(result.chunk_ids) == len(chunks)
    assert result.memory_id is not None

    neighbors = await graph.get_neighbors("document:doc-1", direction="incoming")
    assert any("chunk" in n.id for n in neighbors)


@pytest.mark.asyncio
async def test_pipeline_ingests_text(backends, settings):
    graph, vector_store, memory = backends
    fake_response = json.dumps(
        {
            "entities": [{"name": "RNA-seq", "type": "method"}],
            "relations": [],
        }
    )
    pipeline = CognifyPipeline(
        llm_client=FakeLLMClient(response=fake_response),
        graph_backend=graph,
        vector_store=vector_store,
        memory_backend=memory,
        embedding_provider=FakeEmbeddingProvider(),
        data_dir=settings.data_dir,
        options=None,
    )
    result = await pipeline.ingest_text(
        "RNA-seq is a transcriptomics method used in single-cell analysis.",
        project_id="proj-1",
    )
    assert result.document_id.startswith("doc-")
    assert len(result.chunk_ids) > 0
    assert "RNA-seq" in result.entity_names

    # Duplicate ingestion should be skipped.
    result2 = await pipeline.ingest_text(
        "RNA-seq is a transcriptomics method used in single-cell analysis.",
        project_id="proj-1",
    )
    assert result2.already_processed


@pytest.mark.asyncio
async def test_knowledge_index_search(backends, settings):
    graph, vector_store, memory = backends
    fake_response = json.dumps({"entities": [], "relations": []})
    index = KnowledgeIndex(
        settings=settings,
        llm_client=FakeLLMClient(response=fake_response),
        graph_backend=graph,
        vector_store=vector_store,
        memory_backend=memory,
        embedding_provider=FakeEmbeddingProvider(),
    )
    await index.ingest_text(
        "Single-cell RNA-seq reveals cell type heterogeneity.",
        project_id="proj-1",
    )
    results = await index.search_chunks("single-cell", project_id="proj-1", top_k=3)
    assert len(results) > 0
    await index.close()


def test_knowledge_api_ingest_text(tmp_path):
    from homomics_lab.api.knowledge import router

    settings = Settings(
        data_dir=tmp_path,
        vector_store_backend="sqlite-vec",
        graph_backend="networkx",
    )
    reset_graph_backend()
    reset_vector_store()
    graph = get_graph_backend(settings)
    vector_store = get_vector_store(settings)
    memory = MemoryBackend(settings=settings, embedding_provider=FakeEmbeddingProvider())
    index = KnowledgeIndex(
        settings=settings,
        llm_client=FakeLLMClient(response=json.dumps({"entities": [], "relations": []})),
        graph_backend=graph,
        vector_store=vector_store,
        memory_backend=memory,
        embedding_provider=FakeEmbeddingProvider(),
    )

    app = FastAPI()
    app.include_router(router)
    app.state.knowledge_index = index

    with TestClient(app) as client:
        response = client.post(
            "/ingest",
            json={
                "source_type": "text",
                "source": "Transcriptomics studies RNA expression.",
                "project_id": "proj-api",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["document_id"].startswith("doc-")
        assert data["chunk_count"] > 0

    # Cleanup: close the memory backend (which may warn about cross-thread SQLite).
    import asyncio

    try:
        asyncio.run(memory.close())
    except Exception:
        pass
    reset_vector_store()
    reset_graph_backend()


@pytest.mark.asyncio
async def test_pipeline_graceful_without_llm(backends, settings):
    graph, vector_store, memory = backends
    pipeline = CognifyPipeline(
        llm_client=None,
        graph_backend=graph,
        vector_store=vector_store,
        memory_backend=memory,
        embedding_provider=FakeEmbeddingProvider(),
        data_dir=settings.data_dir,
        options=None,
    )
    result = await pipeline.ingest_text("Just some text without LLM extraction.", project_id="proj-2")
    assert len(result.chunk_ids) > 0
    assert result.entity_names == []
