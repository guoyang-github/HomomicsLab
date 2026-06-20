"""Tests for SemanticMemory hybrid retrieval (dense + FTS5 + RRF)."""

import pytest

from homomics_lab.context.semantic_memory import SemanticMemory


@pytest.fixture
def memory_with_model(tmp_path):
    db_path = tmp_path / "hybrid_memory.db"
    return SemanticMemory(db_path=str(db_path), model_name="all-MiniLM-L6-v2")


@pytest.mark.asyncio
async def test_search_filters_by_project_and_session(memory_with_model):
    mem = memory_with_model
    await mem.add(
        text="project alpha session one",
        memory_type="note",
        project_id="proj_a",
        session_id="sess_1",
    )
    await mem.add(
        text="project beta session one",
        memory_type="note",
        project_id="proj_b",
        session_id="sess_1",
    )
    await mem.add(
        text="project alpha session two",
        memory_type="note",
        project_id="proj_a",
        session_id="sess_2",
    )

    results = await mem.search("project alpha", top_k=5, project_id="proj_a")
    assert len(results) == 2
    assert all(r["metadata"].get("project_id") == "proj_a" for r in results)

    results = await mem.search(
        "project alpha", top_k=5, project_id="proj_a", session_id="sess_2"
    )
    assert len(results) == 1
    assert results[0]["metadata"]["session_id"] == "sess_2"


@pytest.mark.asyncio
async def test_hybrid_search_includes_fts_match(memory_with_model):
    mem = memory_with_model
    await mem.add(
        text="unique keyword xyz123 only appears here",
        memory_type="note",
    )
    await mem.add(
        text="some other generic note",
        memory_type="note",
    )

    results = await mem.search("xyz123", top_k=5)
    assert len(results) >= 1
    assert any("xyz123" in r["text"] for r in results)


@pytest.mark.asyncio
async def test_hybrid_disabled_uses_dense_only(memory_with_model):
    mem = memory_with_model
    await mem.add(
        text="unique keyword abc999",
        memory_type="note",
    )

    results = await mem.search("abc999", top_k=5, hybrid=False)
    assert len(results) >= 1
