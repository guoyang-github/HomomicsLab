"""Tests for semantic memory grooming (prune/consolidate/touch)."""

import pytest

from homomics_lab.context.semantic_memory import SemanticMemory


@pytest.fixture
def memory_with_model(tmp_path):
    db_path = tmp_path / "groom_memory.db"
    return SemanticMemory(db_path=str(db_path), model_name="all-MiniLM-L6-v2")


@pytest.mark.asyncio
async def test_prune_expired_by_ttl(memory_with_model):
    mem = memory_with_model
    await mem.add(text="expires today", memory_type="note", ttl_days=0)
    await mem.add(text="expires later", memory_type="note", ttl_days=30)

    deleted = await mem.prune_stale_memories()
    assert deleted == 1
    remaining = await mem.list_by_type("note")
    assert len(remaining) == 1
    assert remaining[0]["text"] == "expires later"


@pytest.mark.asyncio
async def test_prune_low_importance_stale(memory_with_model):
    mem = memory_with_model
    keep = await mem.add(
        text="recent low importance",
        memory_type="note",
        importance=0.1,
    )
    stale = await mem.add(
        text="old low importance",
        memory_type="note",
        importance=0.1,
    )
    important = await mem.add(
        text="old but important",
        memory_type="note",
        importance=0.9,
    )

    conn = mem._get_conn()
    conn.execute(
        "UPDATE memories SET created_at = date('now', '-40 days'), last_accessed = date('now', '-40 days') WHERE id IN (?, ?)",
        (stale, important),
    )
    conn.commit()

    deleted = await mem.prune_stale_memories(retention_days=30, low_importance_threshold=0.3)
    assert deleted == 1

    assert await mem.get(keep) is not None
    assert await mem.get(stale) is None
    assert await mem.get(important) is not None


@pytest.mark.asyncio
async def test_consolidate_conversation_chunks(memory_with_model):
    mem = memory_with_model
    session_id = "session-abc"
    ids = []
    for i in range(5):
        mid = await mem.add(
            text=f"turn {i}",
            memory_type="conversation",
            metadata={"session_id": session_id, "turn": i},
        )
        ids.append(mid)

    groups = await mem.consolidate_conversation_chunks(session_id=session_id, chunk_size=5)
    assert groups == 1

    remaining = await mem.list_by_type("conversation")
    assert len(remaining) == 1
    merged = remaining[0]
    assert merged["metadata"].get("consolidated") is True
    assert set(merged["metadata"].get("source_ids", [])) == set(ids)
    assert merged["metadata"].get("original_count") == 5
    for i in range(5):
        assert f"turn {i}" in merged["text"]


@pytest.mark.asyncio
async def test_consolidate_respects_session_boundary(memory_with_model):
    mem = memory_with_model
    for i in range(3):
        await mem.add(
            text=f"session-a turn {i}",
            memory_type="conversation",
            metadata={"session_id": "session-a"},
        )
    for i in range(2):
        await mem.add(
            text=f"session-b turn {i}",
            memory_type="conversation",
            metadata={"session_id": "session-b"},
        )

    groups = await mem.consolidate_conversation_chunks(chunk_size=5)
    assert groups == 0


@pytest.mark.asyncio
async def test_search_updates_last_accessed(memory_with_model):
    mem = memory_with_model
    mid = await mem.add(text="searchable content", memory_type="note")

    conn = mem._get_conn()
    conn.execute(
        "UPDATE memories SET last_accessed = date('now', '-10 days') WHERE id = ?",
        (mid,),
    )
    conn.commit()

    results = await mem.search("content", top_k=3)
    assert any(r["id"] == mid for r in results)

    row = conn.execute(
        "SELECT date(last_accessed) FROM memories WHERE id = ?", (mid,)
    ).fetchone()
    assert row is not None
    assert row[0] == conn.execute("SELECT date('now')").fetchone()[0]
