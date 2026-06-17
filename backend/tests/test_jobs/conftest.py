"""Shared fixtures for the jobs test package."""

import pytest
import pytest_asyncio

from homomics_lab.database import Base, async_engine


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_jobs_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
