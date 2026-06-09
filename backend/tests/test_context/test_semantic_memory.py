"""Tests for sqlite-vec based semantic memory."""

import pytest
from pathlib import Path

from homomics_lab.context.semantic_memory import SemanticMemory


@pytest.fixture
def memory(tmp_path):
    db_path = tmp_path / "test_memory.db"
    return SemanticMemory(db_path=str(db_path))


@pytest.fixture
def memory_with_model(tmp_path):
    db_path = tmp_path / "test_memory_model.db"
    return SemanticMemory(db_path=str(db_path), model_name="all-MiniLM-L6-v2")


def test_init_creates_tables(memory):
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
    from homomics_lab.context.semantic_memory import MemoryType

    expected = {"conversation", "task", "experiment", "note"}
    actual = set(MemoryType)
    assert actual == expected
