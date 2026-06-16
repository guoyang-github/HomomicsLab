"""In-memory implementations of queue and pub/sub backends."""

import asyncio
from typing import Callable, Dict, List, Optional

from homomics_lab.hpc.state import ExecutionState

from .base import ExecutionSubscription as BaseExecutionSubscription


class MemoryQueueBackend:
    """FIFO queue of job_ids backed by asyncio.Queue."""

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[str]:
        if timeout is None:
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    async def remove(self, job_id: str) -> int:
        """Remove all occurrences of a job_id from the queue."""
        items: List[str] = []
        while not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        removed = 0
        for item in items:
            if item == job_id:
                removed += 1
            else:
                await self._queue.put(item)
        return removed

    async def close(self) -> None:
        pass


class MemoryPubSubBackend:
    """In-memory pub-sub for execution state updates.

    This is the pre-P3 default implementation extracted into the backend
    abstraction so the rest of the system can remain unchanged.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[ExecutionState], None]]] = {}
        self._history: Dict[str, List[ExecutionState]] = {}
        self._max_history = 100

    def publish(self, job_id: str, state: ExecutionState) -> None:
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        if job_id not in self._history:
            self._history[job_id] = []

        self._history[job_id].append(state)
        if len(self._history[job_id]) > self._max_history:
            self._history[job_id] = self._history[job_id][-self._max_history :]

        for subscriber in self._subscribers[job_id]:
            subscriber(state)

    def subscribe(
        self,
        job_id: str,
        callback: Optional[Callable[[ExecutionState], None]] = None,
    ) -> "MemoryExecutionSubscription":
        return MemoryExecutionSubscription(self, job_id, callback)

    async def latest(self, job_id: str) -> Optional[ExecutionState]:
        history = self._history.get(job_id, [])
        return history[-1] if history else None

    def history(self, job_id: str) -> List[ExecutionState]:
        return list(self._history.get(job_id, []))

    def _add_callback(self, job_id: str, callback: Callable[[ExecutionState], None]) -> None:
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(callback)

    def _remove_callback(
        self,
        job_id: str,
        callback: Callable[[ExecutionState], None],
    ) -> None:
        if job_id in self._subscribers:
            try:
                self._subscribers[job_id].remove(callback)
            except ValueError:
                pass

    async def close(self) -> None:
        pass


class MemoryExecutionSubscription(BaseExecutionSubscription):
    """Async iterator subscription for memory pub-sub."""

    def __init__(
        self,
        pubsub: MemoryPubSubBackend,
        job_id: str,
        callback: Optional[Callable[[ExecutionState], None]] = None,
    ):
        self.pubsub = pubsub
        self.job_id = job_id
        self.external_callback = callback
        self._queue: asyncio.Queue[ExecutionState] = asyncio.Queue()
        self._callback = self._on_state
        self._closed = False

    def _on_state(self, state: ExecutionState) -> None:
        try:
            self._queue.put_nowait(state)
        except asyncio.QueueFull:
            pass
        if self.external_callback:
            self.external_callback(state)

    async def __aenter__(self) -> "MemoryExecutionSubscription":
        self.pubsub._add_callback(self.job_id, self._callback)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.pubsub._remove_callback(self.job_id, self._callback)

    def __aiter__(self):
        return self

    async def __anext__(self) -> ExecutionState:
        if self._closed:
            raise StopAsyncIteration
        return await self._queue.get()
