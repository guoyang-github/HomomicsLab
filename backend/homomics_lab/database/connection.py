from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from homomics_lab.config import settings


# ``check_same_thread`` is SQLite-only. PostgreSQL/MySQL connectors will raise
# if unknown connect_args are passed, so we only include it for SQLite URLs.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    poolclass=NullPool,
    connect_args=_connect_args,
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session():
    async with AsyncSessionLocal() as session:
        yield session
