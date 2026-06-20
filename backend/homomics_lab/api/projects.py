import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homomics_lab.api.auth import get_current_user
from homomics_lab.database.connection import get_async_session
from homomics_lab.database.models import ProjectMember, ProjectRecord
from homomics_lab.projects import ProjectExporter, ProjectImporter
from homomics_lab.projects.permissions import (
    add_project_member,
    require_project_permission,
)
from homomics_lab.api.audit import AuditLogger
from homomics_lab.config import settings
from homomics_lab.provenance.recorder import ProvenanceRecorder
from homomics_lab.provenance.rocrate import ROCrateExporter
from homomics_lab.security import validate_project_id

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _generate_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:8]}"


@router.post("", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    project_id = _generate_project_id()
    record = ProjectRecord(
        project_id=project_id,
        name=project.name,
        description=project.description,
        owner_id=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ProjectResponse(
        id=record.project_id,
        name=record.name,
        description=record.description,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """List projects the current user owns or is a member of."""
    from homomics_lab.config import settings

    stmt = select(ProjectRecord).order_by(ProjectRecord.created_at.desc())
    if settings.auth_enabled:
        # Owned or member of.
        member_stmt = select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
        stmt = stmt.where(
            (ProjectRecord.owner_id == user_id) | (ProjectRecord.project_id.in_(member_stmt))
        )

    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        ProjectResponse(
            id=r.project_id,
            name=r.name,
            description=r.description,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await require_project_permission(project_id, "read", db, user_id)

    result = await db.execute(select(ProjectRecord).where(ProjectRecord.project_id == project_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=record.project_id,
        name=record.name,
        description=record.description,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/{project_id}/export")
async def export_project(
    project_id: str,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Export a project as a .homomics archive file."""
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await require_project_permission(project_id, "read", db, user_id)

    result = await db.execute(select(ProjectRecord).where(ProjectRecord.project_id == project_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found")

    exporter = ProjectExporter(project_id)
    archive_path = exporter.export_to()

    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename=f"{project_id}.homomics",
    )


@router.post("/{project_id}/export/rocrate")
async def export_project_rocrate(
    project_id: str,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Export a project and its provenance as an RO-Crate zip archive."""
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await require_project_permission(project_id, "read", db, user_id)

    result = await db.execute(select(ProjectRecord).where(ProjectRecord.project_id == project_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found")

    recorder = ProvenanceRecorder()
    provenance_records = recorder.list_by_project(project_id)

    crate_dir = Path(settings.data_dir) / "exports" / f"{project_id}_rocrate"
    crate_dir.mkdir(parents=True, exist_ok=True)
    exporter = ROCrateExporter(crate_dir)
    exporter.export(project_id, provenance_records)

    zip_path = crate_dir.with_suffix(".zip")
    shutil.make_archive(str(crate_dir), "zip", root_dir=crate_dir)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{project_id}_rocrate.zip",
    )


@router.post("/import")
async def import_project(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Import a project from a .homomics archive file."""
    if not file.filename or not file.filename.endswith(".homomics"):
        raise HTTPException(status_code=400, detail="File must be a .homomics archive")

    import tempfile

    temp_path = Path(tempfile.gettempdir()) / f"import_{uuid.uuid4().hex}.homomics"
    temp_path.write_bytes(await file.read())

    try:
        importer = ProjectImporter()
        imported_id = importer.import_from(temp_path)

        now = datetime.now(timezone.utc)
        record = ProjectRecord(
            project_id=imported_id,
            name=f"Imported {file.filename[:-9]}",
            description="Imported from archive",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        await db.commit()

        return {"project_id": imported_id, "message": "Project imported successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)


class MemberCreate(BaseModel):
    user_id: str
    role: str = "member"


class MemberResponse(BaseModel):
    project_id: str
    user_id: str
    role: str


@router.post("/{project_id}/members")
async def add_member(
    project_id: str,
    body: MemberCreate,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    await require_project_permission(project_id, "admin", db, user_id)
    try:
        await add_project_member(project_id, body.user_id, body.role, db, added_by=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MemberResponse(project_id=project_id, user_id=body.user_id, role=body.role)


@router.get("/{project_id}/members", response_model=List[MemberResponse])
async def list_members(
    project_id: str,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    await require_project_permission(project_id, "read", db, user_id)
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    members = result.scalars().all()
    return [
        MemberResponse(project_id=m.project_id, user_id=m.user_id, role=m.role)
        for m in members
    ]


@router.get("/{project_id}/audit")
async def get_project_audit_log(
    project_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Return recent audit log entries for a project."""
    await require_project_permission(project_id, "read", db, user_id)
    return {"project_id": project_id, "entries": AuditLogger().list_for_project(project_id, limit=limit)}
