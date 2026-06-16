"""Tests for the execution trace store."""

import pytest
import pytest_asyncio

from homomics_lab.database import Base, async_engine
from homomics_lab.observability.trace_store import TraceStore


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def store():
    return TraceStore()


@pytest.mark.asyncio
async def test_start_and_get_trace(store):
    trace = await store.start_trace(
        trace_id="job_123",
        session_id="sess_1",
        project_id="proj_1",
        root_name="test_job",
    )
    assert trace.trace_id == "job_123"
    assert trace.status == "running"
    assert len(trace.nodes) == 1
    assert trace.nodes[0].node_type == "plan"

    fetched = await store.get_trace("job_123")
    assert fetched is not None
    assert fetched.trace_id == "job_123"


@pytest.mark.asyncio
async def test_add_and_update_node(store):
    await store.start_trace(trace_id="job_123", root_name="test_job")

    node = await store.add_node(
        trace_id="job_123",
        node_type="skill",
        name="scanpy_qc",
        parent_id="root",
        inputs={"value": 10},
    )
    assert node is not None
    assert node.node_type == "skill"
    assert node.parent_id == "root"

    await store.update_node(
        trace_id="job_123",
        node_id=node.node_id,
        status="completed",
        outputs={"result": "ok"},
    )

    trace = await store.get_trace("job_123")
    skill_node = [n for n in trace.nodes if n.node_id == node.node_id][0]
    assert skill_node.status == "completed"
    assert skill_node.outputs == {"result": "ok"}
    assert skill_node.ended_at is not None


@pytest.mark.asyncio
async def test_finish_trace(store):
    await store.start_trace(trace_id="job_123", root_name="test_job")

    finished = await store.finish_trace(
        trace_id="job_123",
        status="failed",
        error_message="something went wrong",
    )
    assert finished is not None
    assert finished.status == "failed"
    assert finished.error_message == "something went wrong"
    assert finished.ended_at is not None
    assert finished.nodes[0].status == "failed"


@pytest.mark.asyncio
async def test_list_recent(store):
    await store.start_trace(trace_id="job_a", root_name="a")
    await store.start_trace(trace_id="job_b", root_name="b")

    recent = await store.list_recent(limit=10)
    assert len(recent) == 2
