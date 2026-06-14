"""Redis-backed implementations of queue and pub/sub backends."""

import asyncio
import json
import logging
from typing import Any, Callable, Optional


async def _async_close(client: Any) -> None:
    close = getattr(client, "aclose", None)
    if close is None:
        close = getattr(client, "close")
    await close()

from homomics_lab.hpc.state import ExecutionState

logger = logging.getLogger(__name__)


def _state_to_json(state: ExecutionState) -> str:
    return json.dumps(state.to_dict())


def _state_from_json(raw: bytes | str) -> ExecutionState:
    data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    return ExecutionState.from_dict(data)


class RedisQueueBackend:
    """Redis list-backed job queue.

    Only job_ids travel through Redis; the full Job payload is still loaded
    from the repository by the worker.
    """

    def __init__(
        self,
        redis,
        queue_key: str = "homomics:queue",
    ):
        self._redis = redis
        self._queue_key = queue_key
        self._closed = False

    async def enqueue(self, job_id: str) -> None:
        await self._redis.lpush(self._queue_key, job_id)

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[str]:
        # BRPOP timeout is in whole seconds in older Redis versions; loop with
        # a short timeout so shutdown remains responsive.
        poll_seconds = max(1, int(timeout or 1))
        while not self._closed:
            result = await self._redis.brpop(self._queue_key, timeout=poll_seconds)
            if result is not None:
                # result is (key, value)
                return result[1].decode() if isinstance(result[1], bytes) else result[1]
            if timeout is not None:
                return None
        return None

    def task_done(self) -> None:
        pass

    async def join(self) -> None:
        pass

    async def remove(self, job_id: str) -> int:
        """Remove a job_id from the queue. Returns number removed."""
        return await self._redis.lrem(self._queue_key, 0, job_id)

    @staticmethod
    def _lock_key(job_id: str) -> str:
        return f"homomics:lock:{job_id}"

    @staticmethod
    def _heartbeat_key(worker_id: str) -> str:
        return f"homomics:worker:{worker_id}"

    async def acquire_lock(self, job_id: str, worker_id: str, ttl: int) -> bool:
        """Try to acquire a distributed lock for a job."""
        acquired = await self._redis.set(
            self._lock_key(job_id), worker_id, nx=True, ex=ttl
        )
        return bool(acquired)

    async def release_lock(self, job_id: str, worker_id: str) -> None:
        """Release the lock only if it is still owned by this worker."""
        key = self._lock_key(job_id)
        current = await self._redis.get(key)
        if current is None:
            return
        if (isinstance(current, bytes) and current.decode() == worker_id) or current == worker_id:
            await self._redis.delete(key)

    async def heartbeat(self, worker_id: str, ttl: int) -> None:
        """Refresh worker liveness key."""
        await self._redis.set(self._heartbeat_key(worker_id), "alive", ex=ttl)

    async def close(self) -> None:
        self._closed = True
        await _async_close(self._redis)


class RedisPubSubBackend:
    """Redis Pub/Sub backend for ExecutionState updates."""

    def __init__(self, redis_url: str, redis=None):
        from redis.asyncio import Redis

        self._redis_url = redis_url
        self._redis = redis or Redis.from_url(redis_url)
        self._latest_prefix = "homomics:latest:"
        self._channel_prefix = "homomics:events:"
        self._latest_ttl = 3600 * 24  # keep latest state for 24h

    @staticmethod
    def _channel(job_id: str) -> str:
        return f"homomics:events:{job_id}"

    @staticmethod
    def _latest_key(job_id: str) -> str:
        return f"homomics:latest:{job_id}"

    def publish(self, job_id: str, state: ExecutionState) -> None:
        """Publish a state update asynchronously.

        This method is kept synchronous for backward compatibility with the
        existing sync callback interfaces; it schedules the actual Redis I/O
        on the running event loop.
        """
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self._publish_async(job_id, state))
        except RuntimeError:
            logger.warning(
                "Cannot publish Redis event for %s without a running event loop", job_id
            )

    async def _publish_async(self, job_id: str, state: ExecutionState) -> None:
        try:
            payload = _state_to_json(state)
            await self._redis.publish(self._channel(job_id), payload)
            await self._redis.set(
                self._latest_key(job_id), payload, ex=self._latest_ttl
            )
        except Exception:
            logger.exception("Failed to publish Redis event for job %s", job_id)

    async def latest(self, job_id: str) -> Optional[ExecutionState]:
        raw = await self._redis.get(self._latest_key(job_id))
        if raw is None:
            return None
        return _state_from_json(raw)

    def subscribe(
        self,
        job_id: str,
        callback: Optional[Callable[[ExecutionState], None]] = None,
    ) -> "RedisExecutionSubscription":
        return RedisExecutionSubscription(
            redis_url=self._redis_url,
            job_id=job_id,
            callback=callback,
        )

    async def close(self) -> None:
        await _async_close(self._redis)


class RedisExecutionSubscription:
    """Async iterator over Redis Pub/Sub messages for a single job."""

    def __init__(
        self,
        redis_url: str,
        job_id: str,
        callback: Optional[Callable[[ExecutionState], None]] = None,
    ):
        from redis.asyncio import Redis

        self._redis_url = redis_url
        self._job_id = job_id
        self._callback = callback
        self._redis = Redis.from_url(redis_url)
        self._pubsub = self._redis.pubsub()
        self._queue: asyncio.Queue[ExecutionState] = asyncio.Queue()
        self._listener_task: Optional[asyncio.Task] = None
        self._closed = False

    async def __aenter__(self) -> "RedisExecutionSubscription":
        channel = RedisPubSubBackend._channel(self._job_id)
        await self._pubsub.subscribe(channel)
        self._listener_task = asyncio.create_task(self._listen())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def _listen(self) -> None:
        try:
            async for message in self._pubsub.listen():
                if self._closed:
                    break
                if message["type"] != "message":
                    continue
                try:
                    state = _state_from_json(message["data"])
                except Exception:
                    logger.exception("Failed to decode Redis event for %s", self._job_id)
                    continue
                if self._callback is not None:
                    try:
                        self._callback(state)
                    except Exception:
                        logger.exception("Error in Redis pub/sub callback")
                try:
                    self._queue.put_nowait(state)
                except asyncio.QueueFull:
                    pass
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Redis pub/sub listener closed for %s", self._job_id)

    def __aiter__(self):
        return self

    async def __anext__(self) -> ExecutionState:
        if self._closed:
            raise StopAsyncIteration
        return await self._queue.get()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._listener_task is not None and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        try:
            await self._pubsub.unsubscribe(
                RedisPubSubBackend._channel(self._job_id)
            )
        except Exception:
            pass
        await _async_close(self._pubsub)
        await _async_close(self._redis)


def create_redis_backends(redis_url: str):
    """Factory for Redis queue + pub/sub backends."""
    from redis.asyncio import Redis

    redis = Redis.from_url(redis_url)
    return RedisQueueBackend(redis), RedisPubSubBackend(redis_url)
