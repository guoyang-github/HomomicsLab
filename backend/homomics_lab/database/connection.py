"""Async database engine and session factory.

The engine is created lazily from ``settings.database_url`` so that tests can
override the setting before the engine is materialized. SQLite uses ``NullPool``
to avoid file-lock issues; PostgreSQL uses a real connection pool.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from homomics_lab.config import settings

# PostgreSQL connection-pool sizing (formerly HOMOMICS_DATABASE_POOL_SIZE /
# HOMOMICS_DATABASE_MAX_OVERFLOW; defaults kept).
DATABASE_POOL_SIZE = 5
DATABASE_MAX_OVERFLOW = 10


# Module-level cache for the engine and session factory.
# Tests can call ``reset_engine()`` to force recreation after changing settings.
_engine = None
_session_factory = None


def _is_sqlite_url(url: str) -> bool:
    """Return True if the URL points to SQLite."""
    return url.startswith("sqlite")


def _connect_args_for_url(url: str) -> dict:
    """Return driver-specific connect_args for the given database URL.

    ``check_same_thread`` is SQLite-only; PostgreSQL/MySQL connectors raise if
    unknown connect_args are passed.
    """
    if _is_sqlite_url(url):
        return {"check_same_thread": False}
    return {}


def create_async_engine_from_settings():
    """Create the async SQLAlchemy engine from current settings."""
    url = settings.database_url
    kwargs = {
        "echo": settings.debug,
        "future": True,
        "connect_args": _connect_args_for_url(url),
    }
    # SQLite does not play well with connection pooling; use NullPool.
    # PostgreSQL uses a real pool for performance (pool sizing is fixed; see
    # DATABASE_POOL_SIZE / DATABASE_MAX_OVERFLOW).
    if _is_sqlite_url(url):
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = DATABASE_POOL_SIZE
        kwargs["max_overflow"] = DATABASE_MAX_OVERFLOW
    return create_async_engine(url, **kwargs)


def get_engine():
    """Return the cached async engine, creating it if necessary."""
    global _engine
    if _engine is None:
        _engine = create_async_engine_from_settings()
    return _engine


def reset_engine() -> None:
    """Clear the cached engine and session factory so they are recreated.

    This is intended for tests and runtime configuration reloads. The previous
    engine is deliberately NOT disposed: module-level aliases (``async_engine``,
    ``AsyncSessionLocal``) and already-imported references may still point at
    it, and disposing it would break them (SQLAlchemy pool "engine disposed"
    errors in unrelated tests). Dropping the cached references is enough to
    force recreation on next ``get_engine()`` call; the abandoned engine is
    reclaimed at process exit.
    """
    global _engine, _session_factory
    _engine = None
    _session_factory = None


def get_session_factory():
    """Return the cached async session factory, creating it if necessary."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# Backward-compatible aliases resolved lazily via module __getattr__ (PEP 562).
# ``async_engine`` / ``AsyncSessionLocal`` used to be bound at import time,
# which went stale whenever the cached engine was reset (tests switching the
# database URL). Attribute access on this module now always resolves the
# current engine/factory. Prefer calling get_engine()/get_session_factory()
# directly in new code.
def __getattr__(name: str):
    if name == "async_engine":
        return get_engine()
    if name == "AsyncSessionLocal":
        return get_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def get_async_session():
    """Yield an async database session for FastAPI dependency injection."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
