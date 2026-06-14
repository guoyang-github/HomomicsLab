"""Tests for the in-memory job queue."""

import pytest

from homomics_lab.jobs import JobQueue


@pytest.mark.asyncio
async def test_enqueue_dequeue():
    queue = JobQueue()
    await queue.enqueue("job_1")
    await queue.enqueue("job_2")

    first = await queue.dequeue()
    assert first == "job_1"
    queue.task_done()

    second = await queue.dequeue()
    assert second == "job_2"
    queue.task_done()


@pytest.mark.asyncio
async def test_dequeue_timeout():
    queue = JobQueue()
    result = await queue.dequeue(timeout=0.1)
    assert result is None
