"""Execution pub/sub facade.

This module is kept for backward compatibility. The canonical implementation
now lives in ``homomics_lab.jobs.backends`` and is selected by
``settings.queue_backend``.
"""

from homomics_lab.jobs.backends import get_pubsub_backend
from homomics_lab.jobs.backends.memory import (
    MemoryExecutionSubscription as ExecutionSubscription,
    MemoryPubSubBackend as ExecutionPubSub,
)


def get_default_pubsub():
    """Return the configured execution pub/sub backend (cached)."""
    return get_pubsub_backend()


__all__ = ["ExecutionPubSub", "ExecutionSubscription", "get_default_pubsub"]
