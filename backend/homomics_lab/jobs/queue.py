"""In-memory job queue with asyncio.

This module is kept for backward compatibility. The canonical implementation
now lives in ``homomics_lab.jobs.backends.memory``.
"""

from homomics_lab.jobs.backends.memory import MemoryQueueBackend as JobQueue

__all__ = ["JobQueue"]
