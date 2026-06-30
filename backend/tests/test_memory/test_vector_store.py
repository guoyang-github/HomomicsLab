"""Tests for vector store backends."""

import pytest

from homomics_lab.context.vector_store.factory import get_vector_store, reset_vector_store
from homomics_lab.context.vector_store.qdrant import QdrantBackend
from homomics_lab.context.vector_store.sqlite_vec import SQLiteVecBackend


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_vector_store()
    yield
    reset_vector_store()


@pytest.mark.asyncio
async def test_qdrant_upsert_and_search(tmp_path, monkeypatch):
    from homomics_lab.config import settings

    monkeypatch.setattr(settings, "vector_store_backend", "qdrant")
    monkeypatch.setattr(settings, "vector_store_url", ":memory:")
    backend = get_vector_store(settings)
    assert isinstance(backend, QdrantBackend)

    await backend.create_collection("test", dimension=3)
    await backend.upsert(
        "test",
        ids=["a", "b"],
        texts=["hello world", "bioinformatics analysis"],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        metadata=[{"type": "greeting"}, {"type": "topic"}],
    )

    results = await backend.search("test", query_embedding=[1.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0].id == "a"
    assert results[0].metadata.get("type") == "greeting"


@pytest.mark.asyncio
async def test_sqlite_vec_upsert_and_search(tmp_path, monkeypatch):
    from homomics_lab.config import settings

    monkeypatch.setattr(settings, "vector_store_backend", "sqlite-vec")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    backend = get_vector_store(settings)
    assert isinstance(backend, SQLiteVecBackend)

    await backend.create_collection("test", dimension=3)
    await backend.upsert(
        "test",
        ids=["a", "b"],
        texts=["hello world", "bioinformatics analysis"],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    )

    results = await backend.search("test", query_embedding=[1.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0].id == "a"
