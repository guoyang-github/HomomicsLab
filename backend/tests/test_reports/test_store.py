"""Tests for the persistent report store."""

import pytest
import pytest_asyncio

from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine
from homomics_lab.reports.generator import ReportGenerator
from homomics_lab.reports.models import SectionType
from homomics_lab.reports.store import ReportStore


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def store():
    return ReportStore()


@pytest.mark.asyncio
async def test_create_and_get_report(store):
    generator = ReportGenerator()
    report = generator.create_report(
        title="Test Report",
        project_name="demo",
        analysis_type="single_cell",
        author="tester",
        parameters={"n_cells": 1000},
        tags=["qc"],
    )

    await store.create(report)
    fetched = await store.get(report.id)

    assert fetched is not None
    assert fetched.title == "Test Report"
    assert fetched.metadata.project_name == "demo"
    assert fetched.metadata.analysis_type == "single_cell"
    assert fetched.metadata.author == "tester"
    assert fetched.metadata.parameters == {"n_cells": 1000}
    assert fetched.metadata.tags == ["qc"]


@pytest.mark.asyncio
async def test_update_report(store):
    generator = ReportGenerator()
    report = generator.create_report(title="Before")
    await store.create(report)

    generator.add_executive_summary(report, "Summary text")
    generator.add_section(
        report,
        title="Methods",
        section_type=SectionType.METHODOLOGY,
        content="Used Scanpy",
    )
    generator.add_analysis_step(
        report,
        name="qc",
        description="Quality control",
        skill_id="scanpy_qc",
        status="completed",
        duration_seconds=60.0,
    )

    await store.update(report)
    fetched = await store.get(report.id)

    assert fetched.summary == "Summary text"
    assert any(s.title == "Methods" for s in fetched.sections)
    assert len(fetched.analysis_steps) == 1
    assert fetched.analysis_steps[0].name == "qc"


@pytest.mark.asyncio
async def test_list_and_delete_reports(store):
    generator = ReportGenerator()
    report_a = generator.create_report(title="A", project_name="p1")
    report_b = generator.create_report(title="B", project_name="p2")
    await store.create(report_a)
    await store.create(report_b)

    all_reports = await store.list_all()
    assert len(all_reports) == 2

    p1_reports = await store.list_all(project_name="p1")
    assert len(p1_reports) == 1
    assert p1_reports[0].title == "A"

    deleted = await store.delete(report_a.id)
    assert deleted is True
    assert await store.get(report_a.id) is None

    deleted_again = await store.delete(report_a.id)
    assert deleted_again is False
