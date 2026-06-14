"""Tests for PlanStore persistence and serialization."""

import uuid

import pytest
import pytest_asyncio

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.database import Base, async_engine
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.plan import Plan, PlanStatus, PlanStore
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def store():
    return PlanStore()


def _make_plan(plan_id: str = None, is_fallback: bool = False) -> Plan:
    if plan_id is None:
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    tree = TaskTree(
        [
            TaskNode(
                id="t1",
                name="qc",
                description="Quality control",
                skills_required=["scanpy_qc"],
            ),
            TaskNode(
                id="t2",
                name="clustering",
                description="Cluster cells",
                skills_required=["scanpy_cluster"],
                dependencies=["t1"],
            ),
        ]
    )
    plan_result = PlanResult(
        phases=[
            Phase(phase_type="qc", description="Quality control"),
            Phase(phase_type="clustering", description="Cluster cells"),
        ],
        strategy_name="test",
        data_state=DataState(),
        is_fallback=is_fallback,
    )
    wm = WorkingMemory()
    wm.add_message(
        ChatMessage(
            id="msg_0",
            type=MessageType.TEXT,
            content="hello",
            sender="user",
        )
    )
    return Plan(
        plan_id=plan_id,
        session_id="sess_1",
        project_id="proj_1",
        status=PlanStatus.PENDING_APPROVAL,
        is_fallback=is_fallback,
        intent_analysis_type="single_cell_analysis",
        intent_complexity="complex",
        plan_result=plan_result,
        task_tree=tree,
        working_memory=wm,
    )


@pytest.mark.asyncio
async def test_create_and_get_plan(store):
    plan = _make_plan()
    created = await store.create(plan)
    assert created.plan_id is not None

    fetched = await store.get(created.plan_id)
    assert fetched is not None
    assert fetched.session_id == "sess_1"
    assert fetched.status == PlanStatus.PENDING_APPROVAL
    assert len(fetched.task_tree.tasks) == 2
    assert fetched.task_tree.tasks[0].name == "qc"
    assert len(fetched.working_memory.messages) == 1
    assert fetched.plan_result.strategy_name == "test"


@pytest.mark.asyncio
async def test_approve_plan(store):
    plan = _make_plan()
    await store.create(plan)

    approved = await store.approve(plan.plan_id, approved_by="user")
    assert approved.status == PlanStatus.APPROVED
    assert approved.approved_by == "user"
    assert approved.approved_at is not None


@pytest.mark.asyncio
async def test_reject_plan(store):
    plan = _make_plan()
    await store.create(plan)

    rejected = await store.reject(plan.plan_id)
    assert rejected.status == PlanStatus.REJECTED


@pytest.mark.asyncio
async def test_list_versions(store):
    parent = _make_plan(plan_id="plan_parent")
    await store.create(parent)

    child = _make_plan(plan_id="plan_child")
    child.parent_plan_id = parent.plan_id
    child.version = 2
    await store.create(child)

    versions = await store.list_versions(parent.plan_id)
    assert len(versions) == 2
    ids = {p.plan_id for p in versions}
    assert ids == {"plan_parent", "plan_child"}


@pytest.mark.asyncio
async def test_plan_round_trip_with_fallback(store):
    plan = _make_plan(is_fallback=True)
    await store.create(plan)

    fetched = await store.get(plan.plan_id)
    assert fetched.is_fallback is True
    assert fetched.plan_result.is_fallback is True
    assert len(fetched.plan_result.phases) == 2
