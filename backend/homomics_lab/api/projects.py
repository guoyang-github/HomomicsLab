from typing import List
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid

from homomics_lab.projects import ProjectExporter, ProjectImporter

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


# In-memory store for MVP
_projects: List[ProjectResponse] = []


@router.post("", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    now = datetime.now().replace(microsecond=0)
    p = ProjectResponse(
        id=f"proj_{uuid.uuid4().hex[:8]}",
        name=project.name,
        description=project.description,
        created_at=now,
        updated_at=now,
    )
    _projects.append(p)
    return p


@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    return _projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    for p in _projects:
        if p.id == project_id:
            return p
    raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/export")
async def export_project(project_id: str):
    """Export a project as a .homomics archive file."""
    project = next((p for p in _projects if p.id == project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    exporter = ProjectExporter(project_id)
    archive_path = exporter.export_to()

    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename=f"{project_id}.homomics",
    )


@router.post("/import")
async def import_project(file: UploadFile = File(...)):
    """Import a project from a .homomics archive file."""
    if not file.filename or not file.filename.endswith(".homomics"):
        raise HTTPException(status_code=400, detail="File must be a .homomics archive")

    import tempfile

    temp_path = Path(tempfile.gettempdir()) / f"import_{uuid.uuid4().hex}.homomics"
    temp_path.write_bytes(await file.read())

    try:
        importer = ProjectImporter()
        imported_id = importer.import_from(temp_path)

        # Register imported project in memory
        now = datetime.now().replace(microsecond=0)
        _projects.append(
            ProjectResponse(
                id=imported_id,
                name=f"Imported {file.filename[:-9]}",
                description="Imported from archive",
                created_at=now,
                updated_at=now,
            )
        )

        return {"project_id": imported_id, "message": "Project imported successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)
