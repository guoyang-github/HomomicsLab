"""Tests for project-level RBAC helpers."""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from homomics_lab.config import settings
from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine
from homomics_lab.database.models import ProjectRecord, Tenant, User
from homomics_lab.projects.permissions import (
    add_project_member,
    is_project_member,
    require_project_permission,
)


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    from homomics_lab.database.connection import get_session_factory

    async with get_session_factory()() as session:
        yield session


@pytest_asyncio.fixture
async def seed_project(db):
    original_auth = settings.auth_enabled
    settings.auth_enabled = True
    tenant = Tenant(id="tenant-1", name="Tenant")
    owner = User(
        id="owner-1",
        tenant_id="tenant-1",
        username="owner",
        hashed_password="x",
        role="analyst",
    )
    member = User(
        id="member-1",
        tenant_id="tenant-1",
        username="member",
        hashed_password="x",
        role="analyst",
    )
    viewer = User(
        id="viewer-1",
        tenant_id="tenant-1",
        username="viewer",
        hashed_password="x",
        role="analyst",
    )
    project = ProjectRecord(
        project_id="proj-1",
        name="Test Project",
        owner_id="owner-1",
    )
    db.add_all([tenant, owner, member, viewer, project])
    await db.commit()
    await add_project_member("proj-1", "member-1", "member", db, added_by="owner-1")
    await add_project_member("proj-1", "viewer-1", "viewer", db, added_by="owner-1")
    yield project
    settings.auth_enabled = original_auth


@pytest.mark.asyncio
async def test_owner_can_read_and_write(db, seed_project):
    await require_project_permission("proj-1", "read", db, "owner-1")
    await require_project_permission("proj-1", "write", db, "owner-1")
    await require_project_permission("proj-1", "delete", db, "owner-1")


@pytest.mark.asyncio
async def test_member_can_read_and_write(db, seed_project):
    await require_project_permission("proj-1", "read", db, "member-1")
    await require_project_permission("proj-1", "write", db, "member-1")


@pytest.mark.asyncio
async def test_viewer_cannot_write(db, seed_project):
    await require_project_permission("proj-1", "read", db, "viewer-1")
    with pytest.raises(HTTPException) as exc_info:
        await require_project_permission("proj-1", "write", db, "viewer-1")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_non_member_is_forbidden(db, seed_project):
    with pytest.raises(HTTPException) as exc_info:
        await require_project_permission("proj-1", "read", db, "stranger")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_project_returns_404(db, seed_project):
    with pytest.raises(HTTPException) as exc_info:
        await require_project_permission("missing", "read", db, "owner-1")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_is_project_member(db, seed_project):
    assert await is_project_member("proj-1", db, "owner-1") is True
    assert await is_project_member("proj-1", db, "member-1") is True
    assert await is_project_member("proj-1", db, "stranger") is False


class TestAuthDisabledBypass:
    @pytest.mark.asyncio
    async def test_permission_bypassed_when_auth_disabled(self, db, seed_project):
        original = settings.auth_enabled
        settings.auth_enabled = False
        try:
            # Even a stranger should pass when auth is disabled.
            await require_project_permission("proj-1", "delete", db, "stranger")
        finally:
            settings.auth_enabled = original
