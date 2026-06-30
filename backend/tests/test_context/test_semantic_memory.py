"""Tests for the modular MemoryBackend semantic memory implementation."""

from pathlib import Path

import pytest

from homomics_lab.config import Settings
from homomics_lab.context.memory_backend import MemoryBackend, MemoryType, create_semantic_memory
from homomics_lab.context.semantic_memory import (
    PostgresSemanticMemory,
    SemanticMemory,
    SQLiteSemanticMemory,
)
from homomics_lab.context.vector_store.factory import reset_vector_store
from homomics_lab.embeddings.factory import reset_embedding_provider
from homomics_lab.context.graph.factory import reset_graph_backend

CACHED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    reset_embedding_provider()
    reset_vector_store()
    reset_graph_backend()
    monkeypatch.setattr("homomics_lab.config.settings.embedding_provider", "sentence_transformers")
    monkeypatch.setattr("homomics_lab.config.settings.embedding_model", CACHED_MODEL)
    monkeypatch.setattr("homomics_lab.config.settings.vector_store_backend", "sqlite-vec")
    monkeypatch.setattr("homomics_lab.config.settings.graph_backend", "networkx")
    return Settings(
        data_dir=tmp_path,
        embedding_provider="sentence_transformers",
        embedding_model=CACHED_MODEL,
        vector_store_backend="sqlite-vec",
        graph_backend="networkx",
    )


@pytest.fixture
def memory(tmp_path, settings):
    return SemanticMemory(db_path=tmp_path / "test_memory.db", settings=settings)


@pytest.fixture
def memory_with_model(tmp_path, settings):
    return SemanticMemory(db_path=tmp_path / "test_memory_model.db", settings=settings)


def test_init_creates_tables(memory):
    assert SemanticMemory is MemoryBackend
    assert SQLiteSemanticMemory is MemoryBackend
    assert PostgresSemanticMemory is MemoryBackend
    assert Path(memory.db_path).exists()


@pytest.mark.asyncio
async def test_add_and_search(memory_with_model):
    mem = memory_with_model

    await mem.add(
        text="单细胞测序质量控制步骤包括过滤低质量细胞和基因",
        memory_type="task",
        metadata={"task_id": "qc_1", "skill": "scanpy_qc"},
    )
    await mem.add(
        text="UMAP降维可视化可以展示细胞群体的分布",
        memory_type="task",
        metadata={"task_id": "viz_1", "skill": "plot_umap"},
    )
    await mem.add(
        text="实验记录：2024年3月15日处理PBMC样本",
        memory_type="experiment",
        metadata={"project_id": "proj_1"},
    )

    results = await mem.search("如何过滤低质量细胞", top_k=3)
    assert len(results) > 0
    assert "质量" in results[0]["text"] or "QC" in results[0]["text"]


@pytest.mark.asyncio
async def test_search_by_type(memory_with_model):
    mem = memory_with_model

    await mem.add(
        text="单细胞分析流程包含质控、降维、聚类",
        memory_type="task",
        metadata={"task_id": "pipeline_1"},
    )
    await mem.add(
        text="单细胞实验使用了10x Genomics平台",
        memory_type="experiment",
        metadata={"experiment_id": "exp_1"},
    )

    results = await mem.search("分析流程", top_k=3, memory_type="task")
    assert len(results) > 0
    assert all(r["memory_type"] == "task" for r in results)


@pytest.mark.asyncio
async def test_get_by_id(memory_with_model):
    mem = memory_with_model

    memory_id = await mem.add(
        text="测试记忆内容",
        memory_type="note",
        metadata={"tag": "test"},
    )

    retrieved = await mem.get(memory_id)
    assert retrieved is not None
    assert retrieved["text"] == "测试记忆内容"
    assert retrieved["memory_type"] == "note"
    assert retrieved["metadata"]["tag"] == "test"


@pytest.mark.asyncio
async def test_delete(memory_with_model):
    mem = memory_with_model

    memory_id = await mem.add(
        text="将被删除的记忆",
        memory_type="note",
    )

    assert await mem.get(memory_id) is not None

    await mem.delete(memory_id)

    assert await mem.get(memory_id) is None


@pytest.mark.asyncio
async def test_list_by_type(memory_with_model):
    mem = memory_with_model

    await mem.add(text="任务1", memory_type="task")
    await mem.add(text="任务2", memory_type="task")
    await mem.add(text="笔记1", memory_type="note")

    tasks = await mem.list_by_type("task")
    assert len(tasks) == 2

    notes = await mem.list_by_type("note")
    assert len(notes) == 1


@pytest.mark.asyncio
async def test_search_returns_scores(memory_with_model):
    mem = memory_with_model

    await mem.add(text="RNA-seq数据分析方法", memory_type="task")
    await mem.add(text="蛋白质组学质谱分析", memory_type="task")

    results = await mem.search("RNA测序", top_k=2)
    assert len(results) > 0
    assert "score" in results[0]
    assert 0 <= results[0]["score"] <= 1


@pytest.mark.asyncio
async def test_empty_search(memory_with_model):
    mem = memory_with_model

    await mem.add(text="单细胞分析", memory_type="task")

    results = await mem.search("quantum physics black hole", top_k=3)
    assert results == []


def test_memory_type_enum():
    expected = {"conversation", "task", "experiment", "note", "preference", "concept"}
    actual = {m.value for m in MemoryType}
    assert actual == expected


def test_factory_returns_backend_with_default_path(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embedding_model=CACHED_MODEL,
        enable_semantic_memory=True,
        vector_store_backend="sqlite-vec",
    )
    memory = create_semantic_memory(settings)
    assert isinstance(memory, MemoryBackend)
    assert memory.db_path == tmp_path / "memory_meta.db"


def test_factory_returns_none_when_disabled(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embedding_model=CACHED_MODEL,
        enable_semantic_memory=False,
    )
    assert create_semantic_memory(settings) is None


def test_factory_returns_none_without_model(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embedding_model=None,
        enable_semantic_memory=True,
    )
    assert create_semantic_memory(settings) is None


@pytest.mark.asyncio
async def test_sqlite_persistence_across_reopen(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embedding_model=CACHED_MODEL,
        vector_store_backend="sqlite-vec",
    )
    mem1 = MemoryBackend(db_path=tmp_path / "persistent_memory.db", settings=settings)
    memory_id = await mem1.add(
        text="persistent RNA sequencing quality control note",
        memory_type="note",
        metadata={"project_id": "p1"},
    )
    await mem1.close()

    reset_vector_store()
    reset_embedding_provider()
    reset_graph_backend()

    mem2 = MemoryBackend(db_path=tmp_path / "persistent_memory.db", settings=settings)
    retrieved = await mem2.get(memory_id)
    assert retrieved is not None
    assert "persistent" in retrieved["text"]

    results = await mem2.search("RNA sequencing quality control", top_k=3)
    assert any("persistent" in r["text"] for r in results)
    await mem2.close()


@pytest.mark.asyncio
async def test_backend_degrades_without_embedding(tmp_path, monkeypatch):
    """When the embedding provider is unavailable, keyword fallback still works."""
    from homomics_lab.embeddings.base import EmbeddingProvider

    class BrokenProvider(EmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 384

        def encode(self, texts):
            raise RuntimeError("offline")

    mem = MemoryBackend(
        db_path=tmp_path / "fallback.db",
        embedding_provider=BrokenProvider(),
        vector_store=None,  # force local keyword fallback
        settings=Settings(data_dir=tmp_path, vector_store_backend="sqlite-vec"),
    )
    await mem.add(text="RNA sequencing QC", memory_type="task")
    results = await mem.search("RNA sequencing", top_k=3)
    assert len(results) > 0
    assert "RNA sequencing QC" in results[0]["text"]


@pytest.mark.asyncio
async def test_postgres_backend_mock():
    """The modular backend no longer has a separate Postgres class; the alias still works."""
    # PostgresSemanticMemory is now an alias for MemoryBackend.
    assert PostgresSemanticMemory is MemoryBackend
