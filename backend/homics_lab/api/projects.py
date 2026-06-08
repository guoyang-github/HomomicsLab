from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

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
