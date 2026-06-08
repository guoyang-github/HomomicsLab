import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from homomics_lab.database.connection import async_engine, get_async_session


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
