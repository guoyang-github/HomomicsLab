from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class SkillSummary(BaseModel):
    id: str
    name: str
    description: str
    category: str
    runtime_type: str
    primary_tool: str


class SkillDetail(SkillSummary):
    version: str
    supported_tools: List[str]
    keywords: List[str]
    dependencies: List[str]
    scripts_dir: Optional[str]
    source: str


@router.get("/", response_model=List[SkillSummary])
async def list_skills(request: Request):
    """List all registered skills."""
    executor = request.app.state.skill_executor
    skills = executor.registry.list_all()

    return [
        SkillSummary(
            id=s.id,
            name=s.name,
            description=s.description,
            category=s.category,
            runtime_type=s.runtime.type,
            primary_tool=s.metadata.get("primary_tool", ""),
        )
        for s in skills
    ]


@router.get("/search", response_model=List[SkillSummary])
async def search_skills(request: Request, q: str):
    """Search skills by keyword."""
    executor = request.app.state.skill_executor
    skills = executor.registry.search(q)

    return [
        SkillSummary(
            id=s.id,
            name=s.name,
            description=s.description,
            category=s.category,
            runtime_type=s.runtime.type,
            primary_tool=s.metadata.get("primary_tool", ""),
        )
        for s in skills
    ]


@router.get("/{skill_id}", response_model=SkillDetail)
async def get_skill(request: Request, skill_id: str):
    """Get detailed information about a specific skill."""
    executor = request.app.state.skill_executor
    skill = executor.registry.get(skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    return SkillDetail(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        category=skill.category,
        runtime_type=skill.runtime.type,
        primary_tool=skill.metadata.get("primary_tool", ""),
        version=skill.version,
        supported_tools=skill.metadata.get("supported_tools", []),
        keywords=skill.metadata.get("keywords", []),
        dependencies=skill.runtime.dependencies,
        scripts_dir=skill.metadata.get("scripts_dir"),
        source=skill.metadata.get("source", "builtin"),
    )


@router.get("/{skill_id}/metrics")
async def get_skill_metrics(request: Request, skill_id: str):
    """Get performance metrics for a skill."""
    executor = request.app.state.skill_executor
    skill = executor.registry.get(skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    if executor.tracker is None:
        return {"skill_id": skill_id, "message": "Metrics tracking not enabled"}

    return executor.tracker.get_stats(skill_id)


@router.get("/{skill_id}/executions")
async def get_skill_executions(request: Request, skill_id: str, limit: int = 100):
    """Get recent execution records for a skill."""
    executor = request.app.state.skill_executor
    skill = executor.registry.get(skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    if executor.tracker is None:
        return []

    records = executor.tracker.get_recent_executions(skill_id=skill_id, limit=limit)
    return [
        {
            "skill_id": r.skill_id,
            "timestamp": r.timestamp,
            "duration_ms": r.duration_ms,
            "success": r.success,
            "output_size": r.output_size,
            "executor_type": r.executor_type,
            "error_message": r.error_message,
        }
        for r in records
    ]


@router.get("/metrics/top")
async def get_top_skills(request: Request, limit: int = 10):
    """Get top skills by execution count."""
    executor = request.app.state.skill_executor

    if executor.tracker is None:
        return []

    return executor.tracker.get_top_skills(limit=limit)
