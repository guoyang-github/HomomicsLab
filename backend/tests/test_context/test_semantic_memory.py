"""Tests for sqlite-vec and PostgreSQL/pgvector semantic memory backends."""

import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homomics_lab.config import Settings
from homomics_lab.context.semantic_memory import (
    MemoryType,
    PostgresSemanticMemory,
    SemanticMemory,
    SQLiteSemanticMemory,
    create_semantic_memory,
)


@pytest.fixture
def memory(tmp_path):
    db_path = tmp_path / "test_memory.db"
    return SemanticMemory(db_path=str(db_path))


@pytest.fixture
def memory_with_model(tmp_path):
    db_path = tmp_path / "test_memory_model.db"
    return SemanticMemory(db_path=str(db_path), model_name="all-MiniLM-L6-v2")


def test_init_creates_tables(memory):
    assert SemanticMemory is SQLiteSemanticMemory
    assert Path(memory.db_path).exists()


@pytest.mark.asyncio
async def test_add_and_search(memory_with_model):
    """Add memories and retrieve by semantic similarity."""
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

    # Search for QC-related content
    results = await mem.search("如何过滤低质量细胞", top_k=3)
    assert len(results) > 0
    # The QC memory should be most relevant
    assert "质量" in results[0]["text"] or "QC" in results[0]["text"]


@pytest.mark.asyncio
async def test_search_by_type(memory_with_model):
    """Filter search results by memory type."""
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

    # Search only tasks
    results = await mem.search("分析流程", top_k=3, memory_type="task")
    assert len(results) > 0
    assert all(r["memory_type"] == "task" for r in results)


@pytest.mark.asyncio
async def test_get_by_id(memory_with_model):
    """Retrieve a specific memory by ID."""
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
    """Delete a memory and verify it's gone."""
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
    """List all memories of a given type."""
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
    """Search results include similarity scores."""
    mem = memory_with_model

    await mem.add(text="RNA-seq数据分析方法", memory_type="task")
    await mem.add(text="蛋白质组学质谱分析", memory_type="task")

    results = await mem.search("RNA测序", top_k=2)
    assert len(results) > 0
    assert "score" in results[0]
    assert 0 <= results[0]["score"] <= 1


@pytest.mark.asyncio
async def test_empty_search(memory_with_model):
    """Search with clearly unrelated query returns empty list."""
    mem = memory_with_model

    await mem.add(text="单细胞分析", memory_type="task")

    # Use an English query that is semantically distant from the stored Chinese text
    results = await mem.search("quantum physics black hole", top_k=3)
    assert results == []


def test_memory_type_enum():
    """All expected memory types are defined."""
    expected = {"conversation", "task", "experiment", "note", "preference", "concept"}
    actual = {m.value for m in MemoryType}
    assert actual == expected


def test_factory_returns_sqlite_with_default_path(tmp_path):
    """Factory creates a persistent SQLite memory at the configured data_dir."""
    settings = Settings(
        data_dir=tmp_path,
        semantic_search_model="all-MiniLM-L6-v2",
        enable_semantic_memory=True,
        semantic_memory_backend="sqlite",
    )
    memory = create_semantic_memory(settings)
    assert isinstance(memory, SQLiteSemanticMemory)
    assert memory.db_path == str(tmp_path / "semantic_memory.db")
    assert memory.db_path != ":memory:"


def test_factory_returns_none_when_disabled(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        semantic_search_model="all-MiniLM-L6-v2",
        enable_semantic_memory=False,
    )
    assert create_semantic_memory(settings) is None


def test_factory_returns_none_without_model(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        semantic_search_model=None,
        enable_semantic_memory=True,
    )
    assert create_semantic_memory(settings) is None


@pytest.mark.asyncio
async def test_sqlite_persistence_across_reopen(tmp_path):
    """Memories written to the SQLite disk path survive close/reopen."""
    db_path = tmp_path / "persistent_memory.db"
    mem1 = SQLiteSemanticMemory(db_path=str(db_path), model_name="all-MiniLM-L6-v2")
    memory_id = await mem1.add(
        text="persistent RNA sequencing quality control note",
        memory_type="note",
        metadata={"project_id": "p1"},
    )
    await mem1.close()

    mem2 = SQLiteSemanticMemory(db_path=str(db_path), model_name="all-MiniLM-L6-v2")
    retrieved = await mem2.get(memory_id)
    assert retrieved is not None
    assert "persistent" in retrieved["text"]

    results = await mem2.search("RNA sequencing quality control", top_k=3)
    assert any("persistent" in r["text"] for r in results)
    await mem2.close()


@pytest.mark.asyncio
async def test_postgres_backend_mock():
    """Postgres backend initialization and add/search flow using mocked asyncpg."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_pool.close = AsyncMock()

    # Make fetchall/fetch return values mutable per call via side_effect below.
    fetch_results = []

    async def _fetch(*args, **kwargs):
        # Return whatever the test has staged; default empty.
        return fetch_results

    async def _fetchrow(*args, **kwargs):
        if "pg_type" in args[0]:
            return {"?column?": 1}
        return None

    mock_conn.fetch.side_effect = _fetch
    mock_conn.fetchrow.side_effect = _fetchrow
    mock_conn.execute.return_value = "INSERT 0 1"

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        memory = PostgresSemanticMemory(
            postgres_url="postgresql://user:pass@localhost/db",
            model_name="all-MiniLM-L6-v2",
        )
        # Force pool creation and schema init.
        await memory._get_pool()

        # Staged dense search result.
        mem_id = uuid.uuid4()
        now = "2024-01-01T00:00:00+00:00"
        fetch_results = [
            {
                "id": mem_id,
                "text": "mocked RNA-seq QC note",
                "memory_type": "note",
                "metadata": '{"project_id": "p1"}',
                "created_at": now,
                "score": 0.95,
            }
        ]

        results = await memory.search("RNA sequencing QC", top_k=3)
        assert len(results) == 1
        assert results[0]["id"] == str(mem_id)
        assert "mocked" in results[0]["text"]

        # Verify init created extension and table.
        execute_calls = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
        assert any("CREATE EXTENSION" in c for c in execute_calls)
        assert any("CREATE TABLE IF NOT EXISTS memories" in c for c in execute_calls)

        await memory.close()


@pytest.mark.asyncio
async def test_postgres_backend_requires_pgvector_extension():
    """Postgres backend raises a clear error when pgvector is unavailable."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    async def _fetchrow(*args, **kwargs):
        # vector type does not exist.
        if "pg_type" in args[0]:
            return None
        return None

    mock_conn.fetchrow.side_effect = _fetchrow
    mock_conn.execute.side_effect = Exception("extension not available")

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        memory = PostgresSemanticMemory(
            postgres_url="postgresql://user:pass@localhost/db",
            model_name="all-MiniLM-L6-v2",
        )
        with pytest.raises(RuntimeError, match="pgvector extension"):
            await memory._get_pool()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith(("postgresql", "postgres")),
    reason="Requires a real PostgreSQL DATABASE_URL",
)
@pytest.mark.asyncio
async def test_postgres_backend_real():
    """Integration test against a real PostgreSQL if DATABASE_URL points to Postgres."""
    memory = PostgresSemanticMemory(
        postgres_url=os.environ["DATABASE_URL"],
        model_name="all-MiniLM-L6-v2",
    )

    # Use a unique project_id so parallel tests do not collide.
    project_id = f"test_{uuid.uuid4().hex}"
    memory_id = await memory.add(
        text="real Postgres integration test memory for RNA-seq QC",
        memory_type="task",
        metadata={"project_id": project_id},
        project_id=project_id,
    )

    retrieved = await memory.get(memory_id)
    assert retrieved is not None
    assert "Postgres integration" in retrieved["text"]

    results = await memory.search("RNA sequencing QC", top_k=3, project_id=project_id)
    assert len(results) > 0
    assert any(memory_id == r["id"] for r in results)

    count = await memory.count(memory_type="task", project_id=project_id)
    assert count >= 1

    deleted = await memory.delete(memory_id)
    assert deleted is True
    assert await memory.get(memory_id) is None

    await memory.close()
