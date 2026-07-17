"""Analysis template management endpoints.

These endpoints expose reusable scenario presets (AnalysisTemplate) that sit
above Domain strategies and guide PlanEngine parameter/skill selection.

They are intentionally separate from ``/api/plan/templates``, which deals with
saved snapshots of concrete PlanResults.
"""

import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
from homomics_lab.api.auth import require_admin
from homomics_lab.api.rate_limit import rate_limit_dependency

router = APIRouter()


class AnalysisTemplateCreate(BaseModel):
    template_id: str
    name: str
    description: str = ""
    domain: str = ""
    applicable_intents: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    phase_defaults: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    preferred_skills: Dict[str, str] = Field(default_factory=dict)
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    sop_ids: List[str] = Field(default_factory=list)
    data_sources: List[Dict[str, Any]] = Field(default_factory=list)
    icon: Optional[str] = None
    version: str = "1.0.0"


class AnalysisTemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    domain: str
    applicable_intents: List[str]
    tags: List[str]
    phase_defaults: Dict[str, Dict[str, Any]]
    preferred_skills: Dict[str, str]
    default_parameters: Dict[str, Any]
    sop_ids: List[str]
    data_sources: List[Dict[str, Any]]
    icon: Optional[str]
    version: str


class AnalysisTemplateListResponse(BaseModel):
    templates: List[AnalysisTemplateResponse]


def _get_store(request: Request) -> AnalysisTemplateStore:
    store = getattr(request.app.state, "analysis_template_store", None)
    if store is None:
        store = AnalysisTemplateStore()
        request.app.state.analysis_template_store = store
    return store


def _template_response(template: AnalysisTemplate) -> AnalysisTemplateResponse:
    return AnalysisTemplateResponse(**template.to_dict())


@router.get("", response_model=AnalysisTemplateListResponse)
async def list_analysis_templates(request: Request):
    """List all available analysis templates."""
    store = _get_store(request)
    templates = store.list_templates()
    return AnalysisTemplateListResponse(
        templates=[_template_response(t) for t in templates]
    )


@router.get("/{template_id}", response_model=AnalysisTemplateResponse)
async def get_analysis_template(template_id: str, request: Request):
    """Return a single analysis template by ID."""
    store = _get_store(request)
    template = store.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_response(template)


@router.post(
    "",
    response_model=AnalysisTemplateResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_admin)],
)
async def create_analysis_template(
    body: AnalysisTemplateCreate,
    request: Request,
):
    """Create or overwrite an analysis template."""
    store = _get_store(request)
    template = AnalysisTemplate(**body.model_dump())
    store.save_template(template)
    return _template_response(template)


@router.put(
    "/{template_id}",
    response_model=AnalysisTemplateResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_admin)],
)
async def update_analysis_template(
    template_id: str,
    body: AnalysisTemplateCreate,
    request: Request,
):
    """Update an existing analysis template."""
    store = _get_store(request)
    if store.get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if body.template_id != template_id:
        raise HTTPException(
            status_code=400,
            detail="template_id in body must match URL",
        )
    template = AnalysisTemplate(**body.model_dump())
    store.save_template(template)
    return _template_response(template)


@router.delete(
    "/{template_id}",
    response_model=Dict[str, bool],
    dependencies=[Depends(rate_limit_dependency), Depends(require_admin)],
)
async def delete_analysis_template(template_id: str, request: Request):
    """Delete an analysis template."""
    store = _get_store(request)
    deleted = store.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}


class TemplateFromExecution(BaseModel):
    plan_id: Optional[str] = None
    task_tree: Optional[Dict[str, Any]] = None
    name: str
    description: str = ""


class TemplateFromOpenAgent(BaseModel):
    phase_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    user_message: str
    name: str
    description: str = ""


class TemplateCreatedResponse(BaseModel):
    template_id: str


def _slugify(name: str) -> str:
    """Create a filesystem-safe template id from a name."""
    base = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE).strip().lower()
    base = re.sub(r"[-\s]+", "_", base)
    return base or "template"


@router.post(
    "/from-execution",
    response_model=TemplateCreatedResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_admin)],
)
async def create_template_from_execution(
    body: TemplateFromExecution,
    request: Request,
):
    """Save a successful execution plan as a reusable analysis template.

    Requires at least ``plan_id`` or ``task_tree`` so the template can capture
    the phase structure.
    """
    if not body.plan_id and not body.task_tree:
        raise HTTPException(
            status_code=400,
            detail="Either plan_id or task_tree is required",
        )

    phase_types: List[str] = []
    applicable_intents: List[str] = []
    if body.task_tree:
        tasks = body.task_tree.get("tasks") or []
        phase_types = [t.get("name") for t in tasks if t.get("name")]
        phase_types = [p for p in phase_types if p]
        analysis_type = body.task_tree.get("intent_analysis_type")
        if analysis_type:
            applicable_intents.append(analysis_type)

    if not applicable_intents and body.plan_id:
        applicable_intents.append("custom_execution")

    template_id = f"{_slugify(body.name)}_{uuid.uuid4().hex[:8]}"
    template = AnalysisTemplate(
        template_id=template_id,
        name=body.name,
        description=body.description or f"Template saved from execution {body.plan_id or ''}",
        applicable_intents=applicable_intents,
        tags=["from_execution"],
        phase_defaults={pt: {} for pt in phase_types},
    )

    store = _get_store(request)
    store.save_template(template)
    return TemplateCreatedResponse(template_id=template_id)


@router.post(
    "/from-open-agent",
    response_model=TemplateCreatedResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_admin)],
)
async def create_template_from_open_agent(
    body: TemplateFromOpenAgent,
    request: Request,
):
    """Save an open-agent run as a lightweight reusable template."""
    phase_types = [
        po.get("phase")
        for po in body.phase_outputs
        if po.get("phase")
    ]
    applicable_intents = [body.user_message] if body.user_message else []

    template_id = f"open_agent_{_slugify(body.name)}_{uuid.uuid4().hex[:8]}"
    template = AnalysisTemplate(
        template_id=template_id,
        name=body.name,
        description=body.description or f"Template saved from open-agent run: {body.user_message}",
        applicable_intents=applicable_intents,
        tags=["from_open_agent"],
        phase_defaults={pt: {} for pt in phase_types},
    )

    store = _get_store(request)
    store.save_template(template)
    return TemplateCreatedResponse(template_id=template_id)
