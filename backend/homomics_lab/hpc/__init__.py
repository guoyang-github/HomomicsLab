"""HPC and workflow execution backends for HomomicsLab."""

__all__ = ["LocalScheduler", "SlurmScheduler", "NextflowRunner", "get_scheduler"]


def __getattr__(name: str):
    """Lazy-load schedulers to avoid circular imports with the pubsub layer."""
    if name in __all__:
        from . import scheduler
        return getattr(scheduler, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
