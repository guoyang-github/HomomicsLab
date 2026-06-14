"""Tests for ExecutionPubSub."""

import asyncio

import pytest

from homomics_lab.hpc.pubsub import ExecutionPubSub
from homomics_lab.hpc.state import ExecutionState


class TestExecutionPubSub:
    @pytest.mark.asyncio
    async def test_publish_and_history(self):
        pubsub = ExecutionPubSub()
        state = ExecutionState(job_id="job_1", status="RUNNING")
        pubsub.publish("job_1", state)

        assert await pubsub.latest("job_1") == state
        assert pubsub.history("job_1") == [state]
        assert await pubsub.latest("unknown") is None

    @pytest.mark.asyncio
    async def test_async_subscription(self):
        pubsub = ExecutionPubSub()
        received = []

        async with pubsub.subscribe("job_1") as subscription:
            pubsub.publish("job_1", ExecutionState(job_id="job_1", status="PENDING"))
            pubsub.publish("job_1", ExecutionState(job_id="job_1", status="RUNNING"))

            for _ in range(2):
                state = await asyncio.wait_for(subscription.__anext__(), timeout=1.0)
                received.append(state.status)

        assert received == ["PENDING", "RUNNING"]

    @pytest.mark.asyncio
    async def test_external_callback(self):
        pubsub = ExecutionPubSub()
        received = []

        def callback(state: ExecutionState) -> None:
            received.append(state.status)

        async with pubsub.subscribe("job_1", callback=callback):
            pubsub.publish("job_1", ExecutionState(job_id="job_1", status="COMPLETED"))
            await asyncio.sleep(0.01)

        assert received == ["COMPLETED"]
