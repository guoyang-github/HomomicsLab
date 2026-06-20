"""Tests for semantic memory consolidation (cluster + summarize)."""

import pytest

from homomics_lab.context.memory_consolidation import MemoryConsolidator
from homomics_lab.context.semantic_memory import SemanticMemory


@pytest.fixture
def consolidator(tmp_path):
    db_path = tmp_path / "consolidation_memory.db"
    memory = SemanticMemory(db_path=str(db_path), model_name="all-MiniLM-L6-v2")
    return MemoryConsolidator(memory, model_name="all-MiniLM-L6-v2")


@pytest.mark.asyncio
async def test_consolidate_similar_conversations(consolidator):
    mem = consolidator.semantic_memory
    # Two semantically similar conversation memories.
    await mem.add(
        text="User asked about PBMC QC filtering parameters.",
        memory_type="conversation",
        project_id="proj_1",
        session_id="sess_1",
    )
    await mem.add(
        text="User followed up on PBMC quality control thresholds.",
        memory_type="conversation",
        project_id="proj_1",
        session_id="sess_1",
    )
    # A third unrelated conversation.
    await mem.add(
        text="User asked about RNA velocity plotting.",
        memory_type="conversation",
        project_id="proj_1",
        session_id="sess_1",
    )

    created = await consolidator.consolidate(
        retention_days=0, min_cluster_size=2, distance_threshold=0.4
    )
    assert created >= 1

    concepts = await mem.list_by_type("concept")
    assert len(concepts) >= 1
    # Original similar conversations should have been removed.
    remaining = await mem.list_by_type("conversation")
    assert len(remaining) <= 1


@pytest.mark.asyncio
async def test_consolidate_respects_retention(consolidator):
    mem = consolidator.semantic_memory
    await mem.add(
        text="recent conversation about QC",
        memory_type="conversation",
    )

    created = await consolidator.consolidate(retention_days=30)
    assert created == 0
    assert await mem.count("conversation") == 1
