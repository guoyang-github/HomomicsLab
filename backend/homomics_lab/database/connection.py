"""Async database engine and session factory.

The engine is created lazily from ``settings.database_url`` so that tests can
override the setting before the engine is materialized. SQLite uses ``NullPool``
to avoid file-lock issues; PostgreSQL uses a real connection pool.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from homomics_lab.config import settings


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
    # PostgreSQL uses a real pool for performance.
    if _is_sqlite_url(url):
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = settings.database_pool_size
        kwargs["max_overflow"] = settings.database_max_overflow
    return create_async_engine(url, **kwargs)


def get_engine():
    """Return the cached async engine, creating it if necessary."""
    global _engine
    if _engine is None:
        _engine = create_async_engine_from_settings()
    return _engine


def reset_engine() -> None:
    """Dispose the cached engine and session factory.

    This is intended for tests and runtime configuration reloads.
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.sync_engine.dispose()
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


# Backward-compatible aliases used by repositories and tests.
# ``async_engine`` is kept for code that expects the old module-level engine.
# It is created lazily on first access via ``get_engine()``.
async_engine = get_engine()
AsyncSessionLocal = get_session_factory()


async def get_async_session():
    """Yield an async database session for FastAPI dependency injection."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
