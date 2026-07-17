"""Verify that Alembic migrations cover the current SQLAlchemy models."""

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from homomics_lab.config import settings
from homomics_lab.database.base import Base


@pytest.mark.asyncio
async def test_migrations_produce_current_schema(tmp_path):
    """Run all Alembic migrations on a fresh DB and assert schema matches models."""
    db_path = tmp_path / "migrated.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    # Apply migrations using Alembic's sync API via subprocess to avoid event-loop
    # conflicts with async SQLAlchemy in the same process.
    import subprocess
    import sys
    from pathlib import Path

    # Resolve backend/ (where alembic.ini lives) from this file so the test
    # works whether pytest is invoked from the repo root or from backend/.
    backend_dir = Path(__file__).resolve().parents[2]

    env = {
        **{k: str(v) for k, v in settings.model_dump().items() if v is not None},
        "HOMOMICS_DATABASE_URL": database_url,
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    # Compare table names.
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        tables = set(await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names()))
    await engine.dispose()

    expected = set(Base.metadata.tables.keys())
    tables.discard("alembic_version")
    assert tables == expected, f"Missing tables: {expected - tables}; Extra tables: {tables - expected}"
