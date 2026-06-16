"""Project-level RBAC helpers.

When authentication is disabled, all users are treated as "anonymous" and
project-level checks are bypassed. When enabled, operations require the user to
be the project owner or a member with a sufficient role.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homomics_lab.api.auth import get_current_user
from homomics_lab.config import settings
from homomics_lab.database.connection import get_async_session
from homomics_lab.database.models import ProjectMember, ProjectRecord


# Role hierarchy (higher index = more permissions).
ROLE_LEVELS = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}

REQUIRED_LEVEL = {
    "read": "viewer",
    "write": "member",
    "admin": "admin",
    "delete": "owner",
}


class PermissionDenied(HTTPException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=403, detail=detail)


async def require_project_permission(
    project_id: str,
    action: str,
    db: AsyncSession,
    user_id: str = Depends(get_current_user),
) -> None:
    """Raise HTTPException if user lacks permission for the action."""
    if not settings.auth_enabled:
        return

    required = REQUIRED_LEVEL.get(action, "owner")
    required_level = ROLE_LEVELS[required]

    # Owner check.
    result = await db.execute(
        select(ProjectRecord.owner_id).where(ProjectRecord.project_id == project_id)
    )
    owner_id = result.scalar_one_or_none()
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if owner_id == user_id:
        return

    # Member role check.
    result = await db.execute(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise PermissionDenied("You are not a member of this project")
    if ROLE_LEVELS.get(role, 0) < required_level:
        raise PermissionDenied(f"Action '{action}' requires role '{required}' or higher")


async def is_project_member(
    project_id: str,
    db: AsyncSession,
    user_id: str,
) -> bool:
    """Return True if user is owner or member of the project."""
    if not settings.auth_enabled:
        return True

    result = await db.execute(
        select(ProjectRecord.owner_id).where(ProjectRecord.project_id == project_id)
    )
    owner_id = result.scalar_one_or_none()
    if owner_id == user_id:
        return True

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def add_project_member(
    project_id: str,
    user_id: str,
    role: str,
    db: AsyncSession,
    added_by: str,
) -> None:
    """Add a member to a project. Only owners/admins should call this."""
    if role not in ROLE_LEVELS:
        raise ValueError(f"Invalid role: {role}")

    # Ensure target user is not already owner.
    result = await db.execute(
        select(ProjectRecord.owner_id).where(ProjectRecord.project_id == project_id)
    )
    owner_id = result.scalar_one_or_none()
    if owner_id == user_id:
        raise ValueError("Project owner is already a member")

    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.add(member)
    await db.commit()


async def remove_project_member(
    project_id: str,
    user_id: str,
    db: AsyncSession,
) -> bool:
    """Remove a member from a project. Returns True if existed."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return False
    await db.delete(member)
    await db.commit()
    return True
