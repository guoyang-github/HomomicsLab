"""Factory for job queue and execution pub/sub backends.

The backend is selected by ``settings.queue_backend``:
  - ``memory``: in-process asyncio.Queue (dev / single-process)
  - ``redis``:  Redis list + pub/sub (production / multi-replica)
"""

from typing import Tuple

from homomics_lab.config import settings

from .base import PubSubBackend, QueueBackend


# Module-level cache so the same backend instances are reused within a process.
_queue_backend: QueueBackend | None = None
_pubsub_backend: PubSubBackend | None = None


def get_queue_backend() -> QueueBackend:
    """Return the configured queue backend (cached)."""
    global _queue_backend
    if _queue_backend is None:
        _queue_backend = _create_queue_backend()
    return _queue_backend


def get_pubsub_backend() -> PubSubBackend:
    """Return the configured pub/sub backend (cached)."""
    global _pubsub_backend
    if _pubsub_backend is None:
        _pubsub_backend = _create_pubsub_backend()
    return _pubsub_backend


def reset_backends() -> None:
    """Clear cached backend instances.

    Useful for tests and runtime configuration changes.
    """
    global _queue_backend, _pubsub_backend
    _queue_backend = None
    _pubsub_backend = None


def _create_queue_backend() -> QueueBackend:
    backend = settings.queue_backend
    if backend == "memory":
        from .memory import MemoryQueueBackend

        return MemoryQueueBackend()
    if backend == "redis":
        from .redis import RedisQueueBackend
        from redis.asyncio import Redis

        return RedisQueueBackend(Redis.from_url(settings.redis_url))
    raise ValueError(f"Unknown queue backend: {backend}")


def _create_pubsub_backend() -> PubSubBackend:
    backend = settings.queue_backend
    if backend == "memory":
        from .memory import MemoryPubSubBackend

        return MemoryPubSubBackend()
    if backend == "redis":
        from .redis import RedisPubSubBackend

        return RedisPubSubBackend(settings.redis_url)
    raise ValueError(f"Unknown queue backend: {backend}")


def create_backends() -> Tuple[QueueBackend, PubSubBackend]:
    """Create and return the configured (queue, pubsub) backends."""
    return get_queue_backend(), get_pubsub_backend()
