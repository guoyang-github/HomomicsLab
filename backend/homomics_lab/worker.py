"""Standalone distributed worker entry point.

Usage:
    python -m homomics_lab.worker
    # or, after installation:
    homomics-worker

The worker connects to the configured Redis queue and pub/sub backend,
loads job payloads from the shared database, and executes them via
TurnRunner/Orchestrator.
"""

import asyncio
import logging
import signal
from typing import Optional

from homomics_lab.bootstrap import bootstrap_worker_context, close_worker_context
from homomics_lab.config import settings
from homomics_lab.jobs import JobService
from homomics_lab.jobs.runner import BackgroundJobRunner
from homomics_lab.logging_config import configure_logging

logger = logging.getLogger(__name__)


class WorkerShutdown:
    def __init__(self):
        self._event = asyncio.Event()

    def set(self):
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self):
        await self._event.wait()


async def _reload_llm_config_loop(
    ctx: dict, shutdown: WorkerShutdown, interval: int = 30
) -> None:
    """Periodically reload LLM config so workers pick up UI changes."""
    llm_client = ctx.get("llm_client")
    if llm_client is None:
        return
    while not shutdown.is_set():
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        if shutdown.is_set():
            break
        try:
            await llm_client.reload_config()
            logger.debug("Worker LLM config reloaded")
        except Exception:
            logger.exception("Failed to reload LLM config in worker")


async def run_worker(shutdown: Optional[WorkerShutdown] = None) -> None:
    """Run a standalone worker until shutdown is signaled."""
    shutdown = shutdown or WorkerShutdown()

    # Initialize the same runtime context as the API process.
    ctx = await bootstrap_worker_context(enable_hot_reload=False)

    # JobService uses the configured queue backend (Redis when enabled).
    memory_manager = ctx.get("memory_manager")
    job_service = JobService(memory_manager=memory_manager)
    runner = BackgroundJobRunner(
        queue=job_service.queue,
        repository=job_service.repository,
        pubsub=job_service.pubsub,
        memory_manager=memory_manager,
    )
    runner.start()
    logger.info("Worker started (backend=%s)", settings.queue_backend)

    # Keep LLM config in sync with the API process / UI.
    reload_task = asyncio.create_task(_reload_llm_config_loop(ctx, shutdown))

    try:
        await shutdown.wait()
    finally:
        logger.info("Worker shutting down...")
        reload_task.cancel()
        try:
            await reload_task
        except asyncio.CancelledError:
            pass
        try:
            await runner.stop(timeout=10.0)
        except Exception:
            logger.exception("Error stopping job runner")
        await job_service.close()
        await close_worker_context(ctx)
        logger.info("Worker stopped")


def main() -> None:
    configure_logging(level=settings.log_level, json_format=True)
    shutdown = WorkerShutdown()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown.set)

    try:
        loop.run_until_complete(run_worker(shutdown))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
