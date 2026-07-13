"""Provenance/lineage API endpoints.

Exposes the workspace lineage graph as an interactive DAG for the frontend.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from homomics_lab.config import settings
from homomics_lab.projects.permissions import require_project_read
from homomics_lab.security import validate_project_id
from homomics_lab.workspace.manager import WorkspaceManager

router = APIRouter()


@router.get("/projects/{project_id}", response_model=Dict[str, Any])
async def get_project_lineage(
    project_id: str,
    _perms: None = Depends(require_project_read),
) -> Dict[str, Any]:
    """Return the data lineage graph for a project.

    The graph contains nodes (raw/intermediate/output artifacts) and edges
    (skill/tool transformations) suitable for rendering as a DAG.
    """
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ws = WorkspaceManager(settings.data_dir, project_id)
    graph = ws.build_lineage_graph()
    return graph.to_dict()
