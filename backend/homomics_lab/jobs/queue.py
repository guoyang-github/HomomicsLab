"""Job queue facade.

This module is kept for backward compatibility. The canonical implementation
now lives in ``homomics_lab.jobs.backends`` and is selected by
``settings.queue_backend``.
"""

from homomics_lab.jobs.backends.memory import MemoryQueueBackend


class JobQueue(MemoryQueueBackend):
    """Backward-compatible in-memory job queue.

    Each instance creates a fresh ``asyncio.Queue``. For the configured
    backend singleton used by the application, use
    ``homomics_lab.jobs.backends.get_queue_backend``.
    """

    def __init__(self) -> None:  # noqa: D401
        super().__init__()


__all__ = ["JobQueue"]
