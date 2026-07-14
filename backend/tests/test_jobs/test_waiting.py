"""Tests for the Waiting Orchestrator: WaitingService + JobService integration."""

from datetime import datetime, timedelta, timezone

import pytest

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.jobs import Job, JobMode, JobRepository, JobService, JobStatus
from homomics_lab.jobs.backends import MemoryPubSubBackend, MemoryQueueBackend
from homomics_lab.jobs.waiting import WaitingService
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@pytest.fixture
def waiting(tmp_path):
    return WaitingService(db_path=tmp_path / "waiting.db")


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


# ---------------------------------------------------------------------------
# WaitingService lifecycle
# ---------------------------------------------------------------------------


def test_register_get_list_cancel(waiting):
    cond = waiting.register("job_1", "manual", {"note": "hold"})
    assert cond.wait_id.startswith("wait_")
    assert cond.status == "pending"

    fetched = waiting.get(cond.wait_id)
    assert fetched is not None
    assert fetched.job_id == "job_1"
    assert fetched.payload == {"note": "hold"}

    waiting.register("job_1", "manual")
    waiting.register("job_2", "manual")
    assert len(waiting.list_pending()) == 3
    assert len(waiting.list_pending(job_id="job_1")) == 2
    assert len(waiting.list_pending(job_id="job_2")) == 1

    assert waiting.cancel(cond.wait_id) is True
    assert waiting.get(cond.wait_id).status == "cancelled"
    # Cancelling a non-pending condition is a no-op.
    assert waiting.cancel(cond.wait_id) is False
    assert len(waiting.list_pending()) == 2


def test_register_rejects_unknown_condition_type(waiting):
    with pytest.raises(ValueError):
        waiting.register("job_1", "carrier_pigeon")


def test_persistence_across_instances(tmp_path):
    db_path = tmp_path / "waiting.db"
    svc1 = WaitingService(db_path=db_path)
    cond = svc1.register("job_1", "webhook", {})

    # Simulate a process restart: a fresh instance over the same database.
    svc2 = WaitingService(db_path=db_path)
    fetched = svc2.get(cond.wait_id)
    assert fetched is not None
    assert fetched.status == "pending"
    assert fetched.payload["token"] == cond.payload["token"]
    assert len(svc2.list_pending(job_id="job_1")) == 1


# ---------------------------------------------------------------------------
# Timer conditions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timer_tick_resumes_overdue_condition(waiting):
    cond = waiting.register("job_1", "timer", {"due_at": _iso(timedelta(seconds=-5))})
    fired = await waiting.tick()
    assert fired == 1
    assert waiting.get(cond.wait_id).status == "resumed"


@pytest.mark.asyncio
async def test_timer_tick_leaves_future_condition_pending(waiting):
    cond = waiting.register("job_1", "timer", {"due_at": _iso(timedelta(hours=1))})
    fired = await waiting.tick()
    assert fired == 0
    assert waiting.get(cond.wait_id).status == "pending"


@pytest.mark.asyncio
async def test_expire_old_marks_expired(waiting):
    cond = waiting.register(
        "job_1", "manual", {"expires_at": _iso(timedelta(seconds=-1))}
    )
    keep = waiting.register("job_1", "manual", {"expires_at": _iso(timedelta(hours=1))})
    assert waiting.expire_old() == 1
    assert waiting.get(cond.wait_id).status == "expired"
    assert waiting.get(keep.wait_id).status == "pending"


class _FakeScheduler:
    """Minimal stand-in for AsyncIOScheduler.add_job/remove_job."""

    def __init__(self):
        self.jobs = {}

    def add_job(self, fn, trigger=None, id=None, name=None, replace_existing=False, max_instances=None):
        self.jobs[id] = fn

    def remove_job(self, job_id):
        self.jobs.pop(job_id, None)


def test_register_schedules_timer_job_and_rebuild_after_restart(tmp_path):
    db_path = tmp_path / "waiting.db"
    scheduler = _FakeScheduler()
    svc = WaitingService(db_path=db_path, scheduler=scheduler)
    cond = svc.register("job_1", "timer", {"due_at": _iso(timedelta(hours=1))})
    assert f"wait_timer_{cond.wait_id}" in scheduler.jobs

    # Restart: a new service instance rebuilds timer jobs from SQLite.
    scheduler2 = _FakeScheduler()
    svc2 = WaitingService(db_path=db_path, scheduler=scheduler2)
    assert svc2.rebuild_timer_jobs() == 1
    assert f"wait_timer_{cond.wait_id}" in scheduler2.jobs

    # Cancelling unschedules the one-shot job.
    assert svc2.cancel(cond.wait_id) is True
    assert f"wait_timer_{cond.wait_id}" not in scheduler2.jobs


# ---------------------------------------------------------------------------
# Webhook conditions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_requires_matching_token(waiting):
    cond = waiting.register("job_1", "webhook", {})
    token = cond.payload["token"]
    assert token  # auto-generated at registration

    assert await waiting.resume(cond.wait_id, token="wrong") is False
    assert await waiting.resume(cond.wait_id) is False
    assert waiting.get(cond.wait_id).status == "pending"

    assert await waiting.resume(cond.wait_id, data={"run_id": "abc"}, token=token) is True
    fetched = waiting.get(cond.wait_id)
    assert fetched.status == "resumed"
    assert fetched.resume_data == {"run_id": "abc"}

    # A resolved condition cannot be resumed twice.
    assert await waiting.resume(cond.wait_id, token=token) is False


@pytest.mark.asyncio
async def test_manual_resume_and_on_resume_callback(tmp_path):
    hits = []
    svc = WaitingService(
        db_path=tmp_path / "waiting.db",
        on_resume=lambda condition: hits.append(condition.wait_id),
    )
    cond = svc.register("job_1", "manual")
    assert await svc.resume(cond.wait_id, data={"ok": True}) is True
    assert hits == [cond.wait_id]
    assert svc.get(cond.wait_id).resume_data == {"ok": True}


# ---------------------------------------------------------------------------
# JobService integration
# ---------------------------------------------------------------------------


@pytest.fixture
def job_service(tmp_path):
    return JobService(
        queue=MemoryQueueBackend(),
        repository=JobRepository(),
        pubsub=MemoryPubSubBackend(),
        waiting_service=WaitingService(db_path=tmp_path / "waiting.db"),
    )


async def _create_running_job(job_service: JobService) -> Job:
    job = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.RUNNING,
        mode=JobMode.WORKFLOW,
        task_tree=TaskTree([TaskNode(id="t1", name="qc", description="QC")]),
        working_memory=WorkingMemory(),
    )
    await job_service.repository.create(job)
    return job


@pytest.mark.asyncio
async def test_suspend_then_resume_requeues_job(job_service):
    job = await _create_running_job(job_service)

    cond = await job_service.suspend_for_event(
        job.job_id, "webhook", {}, resume_task_id="t1"
    )
    persisted = await job_service.get_job(job.job_id)
    assert persisted.status == JobStatus.AWAITING_EVENT
    assert persisted.resume_parameters["wait_id"] == cond.wait_id
    assert persisted.resume_task_id == "t1"

    # Wrong token: condition stays pending, job stays suspended.
    assert await job_service.resume_from_event(cond.wait_id, token="nope") is None
    assert (await job_service.get_job(job.job_id)).status == JobStatus.AWAITING_EVENT

    resumed = await job_service.resume_from_event(
        cond.wait_id, data={"status": "done"}, token=cond.payload["token"]
    )
    assert resumed is not None
    assert resumed.status == JobStatus.QUEUED
    assert resumed.mode == JobMode.RESUME_HITL
    assert resumed.resume_parameters["wait_id"] == cond.wait_id
    assert resumed.resume_parameters["resume_data"] == {"status": "done"}

    # The runner picks the job up again from the queue.
    queued_id = await job_service.queue.dequeue(timeout=0.1)
    assert queued_id == job.job_id


@pytest.mark.asyncio
async def test_timer_tick_requeues_suspended_job(job_service):
    job = await _create_running_job(job_service)
    cond = await job_service.suspend_for_event(
        job.job_id, "timer", {"due_at": _iso(timedelta(seconds=-1))}
    )
    assert (await job_service.get_job(job.job_id)).status == JobStatus.AWAITING_EVENT

    fired = await job_service.waiting.tick()
    assert fired == 1
    assert job_service.waiting.get(cond.wait_id).status == "resumed"
    resumed = await job_service.get_job(job.job_id)
    assert resumed.status == JobStatus.QUEUED
    assert resumed.mode == JobMode.RESUME_HITL
    # resume_task_id falls back to the first task when not provided.
    assert resumed.resume_task_id == "t1"

    queued_id = await job_service.queue.dequeue(timeout=0.1)
    assert queued_id == job.job_id


@pytest.mark.asyncio
async def test_suspended_job_is_not_executed_by_runner(job_service):
    """A job dequeued while AWAITING_EVENT is skipped, not executed."""
    from homomics_lab.jobs.runner import BackgroundJobRunner

    job = await _create_running_job(job_service)
    await job_service.suspend_for_event(job.job_id, "manual")
    await job_service.queue.enqueue(job.job_id)

    runner = BackgroundJobRunner(
        queue=job_service.queue,
        repository=job_service.repository,
        pubsub=job_service.pubsub,
        runner_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("runner must not execute a suspended job")
        ),
    )
    await runner._execute_job(await job_service.queue.dequeue(timeout=0.1))
    assert (await job_service.get_job(job.job_id)).status == JobStatus.AWAITING_EVENT
