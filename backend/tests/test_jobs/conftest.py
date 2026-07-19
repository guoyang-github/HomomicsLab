"""Shared fixtures for the jobs test package."""

import pytest_asyncio

from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_jobs_tables():
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
