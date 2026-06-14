"""In-memory pub-sub for execution state updates.

This module is kept for backward compatibility. The canonical implementation
now lives in ``homomics_lab.jobs.backends.memory``.
"""

from homomics_lab.jobs.backends.memory import (
    MemoryExecutionSubscription as ExecutionSubscription,
    MemoryPubSubBackend as ExecutionPubSub,
)

_default_pubsub = ExecutionPubSub()


def get_default_pubsub() -> ExecutionPubSub:
    """Return the global execution pubsub instance."""
    return _default_pubsub


__all__ = ["ExecutionPubSub", "ExecutionSubscription", "get_default_pubsub"]
