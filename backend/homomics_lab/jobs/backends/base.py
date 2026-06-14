"""Abstract backends for the job queue and execution progress bus."""

from __future__ import annotations

from typing import AsyncIterator, Callable, Optional, Protocol


class QueueBackend(Protocol):
    """FIFO queue that only holds job references (job_ids)."""

    async def enqueue(self, job_id: str) -> None:
        ...

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[str]:
        ...

    def task_done(self) -> None:
        ...

    async def join(self) -> None:
        ...

    async def close(self) -> None:
        ...


class PubSubBackend(Protocol):
    """Publish/subscribe bus for ExecutionState updates."""

    def publish(self, job_id: str, state: "ExecutionState") -> None:
        ...

    def subscribe(
        self,
        job_id: str,
        callback: Optional[Callable[["ExecutionState"], None]] = None,
    ) -> "ExecutionSubscription":
        ...

    async def latest(self, job_id: str) -> Optional["ExecutionState"]:
        ...

    async def close(self) -> None:
        ...


class ExecutionSubscription(Protocol):
    """Async iterator over execution state updates for a single job."""

    async def __aenter__(self) -> "ExecutionSubscription":
        ...

    async def __aexit__(self, exc_type, exc, tb) -> None:
        ...

    def __aiter__(self) -> AsyncIterator["ExecutionState"]:
        ...

    async def __anext__(self) -> "ExecutionState":
        ...

    async def close(self) -> None:
        ...
