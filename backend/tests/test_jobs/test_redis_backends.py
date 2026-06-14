"""Tests for Redis-backed queue and pub/sub backends using fakeredis."""

import asyncio

import pytest
from fakeredis import FakeAsyncRedis, FakeServer

from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.backends.redis import (
    RedisPubSubBackend,
    RedisQueueBackend,
)


@pytest.fixture
def fake_redis(monkeypatch):
    """Patch redis.asyncio.Redis.from_url to return a shared FakeAsyncRedis."""
    server = FakeServer()
    server_redis = FakeAsyncRedis(server=server)

    def _from_url(url, **kwargs):
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(
        "redis.asyncio.Redis.from_url",
        _from_url,
    )
    return server_redis


@pytest.mark.asyncio
async def test_redis_queue_enqueue_dequeue(fake_redis):
    queue = RedisQueueBackend(fake_redis)
    await queue.enqueue("job_1")
    await queue.enqueue("job_2")

    first = await queue.dequeue(timeout=1)
    second = await queue.dequeue(timeout=1)
    assert {first, second} == {"job_1", "job_2"}

    assert await queue.dequeue(timeout=0.1) is None
    await queue.close()


@pytest.mark.asyncio
async def test_redis_queue_remove(fake_redis):
    queue = RedisQueueBackend(fake_redis)
    await queue.enqueue("job_a")
    await queue.enqueue("job_b")

    removed = await queue.remove("job_a")
    assert removed == 1

    assert await queue.dequeue(timeout=1) == "job_b"
    assert await queue.dequeue(timeout=0.1) is None
    await queue.close()


@pytest.mark.asyncio
async def test_redis_pubsub_publish_and_subscribe(fake_redis):
    pubsub = RedisPubSubBackend("redis://localhost")

    state = ExecutionState(job_id="job_1", status="RUNNING")
    pubsub.publish("job_1", state)
    # Give the scheduled publish task a chance to run.
    await asyncio.sleep(0.05)

    latest = await pubsub.latest("job_1")
    assert latest is not None
    assert latest.status == "RUNNING"

    received = []
    async with pubsub.subscribe("job_1") as subscription:
        pubsub.publish("job_1", ExecutionState(job_id="job_1", status="COMPLETED"))
        received.append(await asyncio.wait_for(subscription.__anext__(), timeout=1.0))

    assert received[0].status == "COMPLETED"
    await pubsub.close()


@pytest.mark.asyncio
async def test_redis_queue_lock(fake_redis):
    queue = RedisQueueBackend(fake_redis)

    assert await queue.acquire_lock("job_x", "worker_1", ttl=10)
    assert not await queue.acquire_lock("job_x", "worker_2", ttl=10)

    await queue.release_lock("job_x", "worker_1")
    assert await queue.acquire_lock("job_x", "worker_2", ttl=10)
    await queue.close()
