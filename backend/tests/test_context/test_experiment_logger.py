"""Tests for experiment logger and MEMORY.md generation."""

import pytest

from homomics_lab.context.experiment_logger import ExperimentLogger


@pytest.fixture
def logger(tmp_path):
    db_path = tmp_path / "exp.db"
    return ExperimentLogger(
        project_id="test_proj",
        db_path=str(db_path),
    )


@pytest.mark.asyncio
async def test_record_note(logger):
    """Recording a note returns an ID and stores it."""
    note_id = await logger.record(
        text="QC removed 12% of cells",
        step="quality_control",
        tags=["QC", "scanpy"],
        metadata={"cells_before": 10000, "cells_after": 8800},
    )

    assert note_id > 0

    retrieved = await logger.get(note_id)
    assert retrieved["text"] == "QC removed 12% of cells"
    assert retrieved["step"] == "quality_control"
    assert "QC" in retrieved["tags"]
    assert retrieved["metadata"]["cells_after"] == 8800


@pytest.mark.asyncio
async def test_list_by_time_range(logger):
    """Notes can be filtered by time range."""
    await logger.record(text="Note A", step="step1")
    await logger.record(text="Note B", step="step2")
    await logger.record(text="Note C", step="step1")

    # All notes
    all_notes = await logger.list_by_time_range()
    assert len(all_notes) == 3

    # Filter by step
    step1_notes = await logger.list_by_time_range(step="step1")
    assert len(step1_notes) == 2


@pytest.mark.asyncio
async def test_search_by_tag(logger):
    """Tag search finds matching notes."""
    await logger.record(text="RNA-seq result", tags=["RNA-seq", "DE"])
    await logger.record(text="ATAC-seq result", tags=["ATAC-seq"])
    await logger.record(text="Another RNA", tags=["RNA-seq"])

    results = await logger.search_by_tag("RNA-seq")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_generate_memory_md(logger, tmp_path):
    """MEMORY.md is generated with correct structure."""
    await logger.record(
        text="First observation",
        step="quality_control",
        tags=["QC"],
    )
    await logger.record(
        text="Second observation",
        step="clustering",
        tags=["UMAP"],
    )

    output_path = tmp_path / "MEMORY.md"
    content = logger.generate_memory_md(output_path=output_path)

    assert output_path.exists()
    assert "# Experiment Log: test_proj" in content
    assert "First observation" in content
    assert "Second observation" in content
    assert "quality_control" in content
    assert "clustering" in content
    assert "`QC`" in content
    assert "Total entries: 2" in content


@pytest.mark.asyncio
async def test_hybrid_search_fallback(logger):
    """Without semantic memory, hybrid search falls back to text LIKE."""
    await logger.record(text="Single-cell RNA analysis")
    await logger.record(text="Bulk RNA-seq pipeline")
    await logger.record(text="Proteomics workflow")

    results = await logger.hybrid_search("RNA")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_record_without_optional_fields(logger):
    """Recording with only text works."""
    note_id = await logger.record(text="Minimal note")

    retrieved = await logger.get(note_id)
    assert retrieved["text"] == "Minimal note"
    assert retrieved["step"] is None
    assert retrieved["tags"] == []
    assert retrieved["metadata"] == {}
