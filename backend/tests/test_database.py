import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool, QueuePool

from homomics_lab.database.connection import (
    async_engine,
    create_async_engine_from_settings,
    get_async_session,
    reset_engine,
)


@pytest.mark.asyncio
async def test_database_connection():
    async with async_engine.connect() as conn:
        result = await conn.exec_driver_sql("SELECT 1")
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_get_session():
    async for session in get_async_session():
        assert isinstance(session, AsyncSession)
        break


def test_sqlite_uses_null_pool_and_connect_args(monkeypatch):
    monkeypatch.setattr("homomics_lab.database.connection.settings.database_url", "sqlite+aiosqlite:///./test.db")
    reset_engine()
    engine = create_async_engine_from_settings()
    assert isinstance(engine.pool, NullPool)
    # The ``check_same_thread`` connect arg is applied by the dialect, not
    # stored directly on the engine object.
    assert engine.url.drivername == "sqlite+aiosqlite"


def test_postgres_uses_queue_pool(monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.database.connection.settings.database_url",
        "postgresql+asyncpg://user:pass@localhost/db",
    )
    reset_engine()
    engine = create_async_engine_from_settings()
    assert isinstance(engine.pool, QueuePool)
    assert engine.url.drivername == "postgresql+asyncpg"
