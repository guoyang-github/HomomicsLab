from typing import List
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from homomics_lab.database.connection import get_async_session
from homomics_lab.database.models import ProjectRecord
from homomics_lab.projects import ProjectExporter, ProjectImporter
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
):
    now = datetime.now(timezone.utc)
    project_id = _generate_project_id()
    record = ProjectRecord(
        project_id=project_id,
        name=project.name,
        description=project.description,
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
async def list_projects(db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(ProjectRecord).order_by(ProjectRecord.created_at.desc()))
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
):
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
):
    """Export a project as a .homomics archive file."""
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@router.post("/import")
async def import_project(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
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
