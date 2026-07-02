"""Plan approval and inspection endpoints."""

import uuid
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import PlanResult
from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
from homomics_lab.api.auth import require_analyst_or_admin
from homomics_lab.api.rate_limit import rate_limit_dependency
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.jobs import JobMode, JobService
from homomics_lab.metrics import (
    record_plan_approval,
    record_plan_rationale_request,
    record_plan_strategy_switch,
)
from homomics_lab.plan import (
    Plan,
    PlanApprovalRequest,
    PlanPresenter,
    PlanStatus,
    PlanStore,
)
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree

router = APIRouter()


class SaveTemplateRequest(BaseModel):
    name: str


class TemplateResponse(BaseModel):
    template_id: str
    name: str
    created_at: Optional[str] = None


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]


class LoadTemplateRequest(BaseModel):
    session_id: str
    project_id: str


class PlanApproveResponse(BaseModel):
    plan_id: str
    status: str
    job_id: str | None = None
    new_plan_id: str | None = None


class PlanListResponse(BaseModel):
    plans: List[Dict[str, Any]]


class PlanDiffResponse(BaseModel):
    plan_a_id: str
    plan_b_id: str
    differences: List[Dict[str, Any]]


class PlanJobResponse(BaseModel):
    plan_id: str
    job_id: Optional[str] = None
    job_status: Optional[str] = None


def _get_plan_store(request: Request) -> PlanStore:
    return getattr(request.app.state, "plan_store", None) or PlanStore()


def _get_job_service(request: Request) -> JobService:
    return getattr(request.app.state, "job_service", None) or JobService()


@router.post(
    "/{plan_id}/approve",
    response_model=PlanApproveResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_analyst_or_admin)],
)
async def approve_plan(
    plan_id: str,
    request: PlanApprovalRequest,
    http_request: Request,
):
    """Approve a pending plan.

    If modifications are provided, a new plan version is created first and
    the new version is approved and enqueued.
    """
    plan_store = _get_plan_store(http_request)
    job_service = _get_job_service(http_request)

    plan = await plan_store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.status != PlanStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Plan is not awaiting approval (status={plan.status})",
        )

    if not request.approved:
        rejected = await plan_store.reject(plan_id)
        return PlanApproveResponse(
            plan_id=plan_id,
            status=rejected.status,
        )

    target_plan = plan
    new_plan_id = None
    if request.modifications:
        target_plan = await plan_store.modify(
            plan_id,
            modifications=request.modifications,
            approved=True,
            approved_by="user",
        )
        new_plan_id = target_plan.plan_id

    approved = await plan_store.approve(target_plan.plan_id, approved_by="user")
    record_plan_approval("approved")
    working_memory = approved.working_memory or WorkingMemory()

    mode = (
        JobMode.SINGLE_STEP if len(approved.task_tree.tasks) == 1 else JobMode.WORKFLOW
    )
    job = await job_service.create_job(
        session_id=approved.session_id,
        project_id=approved.project_id,
        working_memory=working_memory,
        task_tree=approved.task_tree,
        mode=mode,
        plan_id=approved.plan_id,
    )

    return PlanApproveResponse(
        plan_id=approved.plan_id,
        status=approved.status,
        job_id=job.job_id,
        new_plan_id=new_plan_id,
    )


@router.post(
    "/{plan_id}/reject",
    response_model=PlanApproveResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_analyst_or_admin)],
)
async def reject_plan(
    plan_id: str,
    http_request: Request,
):
    """Reject a pending plan."""
    plan_store = _get_plan_store(http_request)

    plan = await plan_store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.status != PlanStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Plan is not awaiting approval (status={plan.status})",
        )

    rejected = await plan_store.reject(plan_id)
    record_plan_approval("rejected")
    return PlanApproveResponse(
        plan_id=plan_id,
        status=rejected.status,
    )


@router.post(
    "/{plan_id}/modify",
    response_model=PlanApproveResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_analyst_or_admin)],
)
async def modify_plan(
    plan_id: str,
    request: PlanApprovalRequest,
    http_request: Request,
):
    """Create a new plan version with modifications.

    If `approved` is true, the new version is immediately approved and enqueued.
    """
    plan_store = _get_plan_store(http_request)
    job_service = _get_job_service(http_request)

    plan = await plan_store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.status != PlanStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Plan is not awaiting approval (status={plan.status})",
        )

    new_plan = await plan_store.modify(
        plan_id,
        modifications=request.modifications,
        approved=request.approved,
        approved_by="user" if request.approved else None,
    )

    if not request.approved:
        return PlanApproveResponse(
            plan_id=new_plan.plan_id,
            status=new_plan.status,
            new_plan_id=new_plan.plan_id,
        )

    approved = await plan_store.approve(new_plan.plan_id, approved_by="user")
    record_plan_approval("approved_modified")
    working_memory = approved.working_memory or WorkingMemory()
    mode = (
        JobMode.SINGLE_STEP if len(approved.task_tree.tasks) == 1 else JobMode.WORKFLOW
    )
    job = await job_service.create_job(
        session_id=approved.session_id,
        project_id=approved.project_id,
        working_memory=working_memory,
        task_tree=approved.task_tree,
        mode=mode,
        plan_id=approved.plan_id,
    )

    return PlanApproveResponse(
        plan_id=approved.plan_id,
        status=approved.status,
        job_id=job.job_id,
        new_plan_id=new_plan.plan_id,
    )


@router.get("/session/{session_id}", response_model=PlanListResponse)
async def list_session_plans(session_id: str, request: Request):
    """List all plans for a session, newest first."""
    plan_store = _get_plan_store(request)
    plans = await plan_store.list_by_session(session_id)
    return {"plans": [PlanPresenter.to_user_payload(p) for p in plans]}


@router.get("/{plan_id}")
async def get_plan(plan_id: str, request: Request):
    """Return a human-readable plan payload."""
    plan_store = _get_plan_store(request)

    plan = await plan_store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    return PlanPresenter.to_user_payload(plan)


@router.get("/{plan_id}/versions")
async def get_plan_versions(plan_id: str, request: Request):
    """Return the version chain for a plan."""
    plan_store = _get_plan_store(request)

    versions = await plan_store.list_versions(plan_id)
    return {"plans": [PlanPresenter.to_user_payload(p) for p in versions]}


@router.get("/{plan_id}/diff")
async def diff_plans(
    plan_id: str,
    request: Request,
    other: Optional[str] = None,
):
    """Return differences between a plan and another version.

    If `other` is omitted, the parent plan is used as the baseline.
    """
    plan_store = _get_plan_store(request)

    plan_a = await plan_store.get(plan_id)
    if plan_a is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_b_id = other or plan_a.parent_plan_id
    if plan_b_id is None:
        raise HTTPException(
            status_code=400,
            detail="No baseline plan available for diff",
        )

    plan_b = await plan_store.get(plan_b_id)
    if plan_b is None:
        raise HTTPException(status_code=404, detail="Baseline plan not found")

    differences = PlanStore.diff(plan_a, plan_b)
    return PlanDiffResponse(
        plan_a_id=plan_a.plan_id,
        plan_b_id=plan_b.plan_id,
        differences=differences,
    )


@router.get("/{plan_id}/job", response_model=PlanJobResponse)
async def get_plan_job(plan_id: str, request: Request):
    """Return the latest job associated with a plan."""
    plan_store = _get_plan_store(request)
    job_service = _get_job_service(request)

    plan = await plan_store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    jobs = await job_service.repository.list_by_session(plan.session_id)
    matching = [j for j in jobs if j.plan_id == plan_id]
    if not matching:
        return PlanJobResponse(plan_id=plan_id, job_id=None, job_status=None)

    latest = matching[0]
    return PlanJobResponse(
        plan_id=plan_id,
        job_id=latest.job_id,
        job_status=latest.status.value,
    )


@router.post("/{plan_id}/template", response_model=TemplateResponse)
async def save_plan_template(
    plan_id: str,
    request: SaveTemplateRequest,
    http_request: Request,
):
    """Save a plan as a reusable template."""
    plan_store = _get_plan_store(http_request)
    try:
        template_id = await plan_store.save_template(plan_id, request.name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TemplateResponse(
        template_id=template_id,
        name=request.name,
    )


@router.get("/templates", response_model=TemplateListResponse)
async def list_plan_templates(http_request: Request):
    """List all reusable plan templates."""
    plan_store = _get_plan_store(http_request)
    templates = await plan_store.list_templates()
    return TemplateListResponse(
        templates=[
            TemplateResponse(
                template_id=t["template_id"],
                name=t["name"],
                created_at=t.get("created_at"),
            )
            for t in templates
        ]
    )


@router.post("/template/{template_id}/load", response_model=PlanApproveResponse)
async def load_plan_template(
    template_id: str,
    request: LoadTemplateRequest,
    http_request: Request,
):
    """Load a template as a new pending plan."""
    plan_store = _get_plan_store(http_request)
    try:
        new_plan = await plan_store.load_template(
            template_id,
            session_id=request.session_id,
            project_id=request.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlanApproveResponse(
        plan_id=new_plan.plan_id,
        status=new_plan.status,
    )


class SwitchStrategyRequest(BaseModel):
    strategy_name: Optional[str] = None
    template_id: Optional[str] = None
    preserve_user_modifications: bool = True


def _get_plan_engine(http_request: Request) -> PlanEngine:
    skill_executor = getattr(http_request.app.state, "skill_executor", None)
    skill_registry = (
        cast(SkillRegistry, skill_executor.registry)
        if skill_executor is not None
        else SkillRegistry()
    )
    return PlanEngine(
        skill_registry=skill_registry,
        skill_dag=getattr(http_request.app.state, "skill_dag", None),
        cbkb=getattr(http_request.app.state, "cbkb", None),
        capability_index=getattr(http_request.app.state, "capability_index", None),
        strategy_library=getattr(http_request.app.state, "strategy_library", None),
    )


def _get_template_store(http_request: Request) -> AnalysisTemplateStore:
    return (
        getattr(http_request.app.state, "analysis_template_store", None)
        or AnalysisTemplateStore()
    )


def _build_task_tree(plan_result: PlanResult) -> TaskTree:
    """Convert a PlanResult into a linear TaskTree."""
    tasks: list[TaskNode] = []
    prev_id: Optional[str] = None
    for phase in plan_result.phases:
        task_id = phase.phase_type
        dependencies: list[str] = []
        if prev_id is not None:
            dependencies.append(prev_id)
        tasks.append(
            TaskNode(
                id=task_id,
                name=phase.phase_type,
                description=phase.description,
                phase=phase.phase_type,
                skills_required=[phase.selected_skill.id]
                if phase.selected_skill is not None
                else [],
                parameters=dict(phase.parameters),
                dependencies=dependencies,
            )
        )
        prev_id = task_id
    return TaskTree(tasks=tasks)


def _merge_user_modifications(
    new_plan_result: PlanResult,
    old_plan_result: PlanResult,
) -> None:
    """Carry forward user-modified phase parameters into a regenerated plan."""
    old_params = {p.phase_type: dict(p.parameters) for p in old_plan_result.phases}
    for phase in new_plan_result.phases:
        if phase.phase_type in old_params:
            merged = {**phase.parameters, **old_params[phase.phase_type]}
            phase.parameters = merged


@router.get("/{plan_id}/rationale")
async def get_plan_rationale(plan_id: str, http_request: Request):
    """Return the auditable strategy trace for a plan."""
    plan_store = _get_plan_store(http_request)
    plan = await plan_store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    trace = plan.plan_result.strategy_trace
    if trace is None:
        raise HTTPException(
            status_code=404, detail="No strategy trace available for this plan"
        )
    record_plan_rationale_request(plan.plan_result.strategy_name)
    return {
        "plan_id": plan.plan_id,
        "strategy_name": plan.plan_result.strategy_name,
        "strategy_trace": trace.to_dict(),
        "reproducibility_context": plan.plan_result.reproducibility_context,
    }


@router.post("/{plan_id}/switch-strategy", response_model=PlanApproveResponse)
async def switch_plan_strategy(
    plan_id: str,
    request: SwitchStrategyRequest,
    http_request: Request,
):
    """Regenerate a pending plan under a different strategy or template.

    The original plan is kept as the parent; a new plan version is created
    and returned in ``PENDING_APPROVAL`` state.
    """
    plan_store = _get_plan_store(http_request)
    plan = await plan_store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != PlanStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail="Can only switch strategy for plans awaiting approval",
        )

    intent_data = plan.original_intent or {
        "analysis_type": plan.intent_analysis_type,
        "complexity": plan.intent_complexity or "complex",
    }
    intent = UserIntent(**intent_data)
    data_state = plan.plan_result.data_state

    template: Optional[AnalysisTemplate] = None
    if request.template_id is not None:
        template_store = _get_template_store(http_request)
        template = template_store.get_template(request.template_id)
        if template is None:
            raise HTTPException(
                status_code=404,
                detail=f"Template {request.template_id} not found",
            )

    plan_engine = _get_plan_engine(http_request)
    new_plan_result = await plan_engine.plan(
        intent,
        data_state=data_state,
        project_id=plan.project_id,
        template=template,
        strategy_name=request.strategy_name,
    )

    if request.preserve_user_modifications:
        _merge_user_modifications(new_plan_result, plan.plan_result)

    new_task_tree = _build_task_tree(new_plan_result)
    new_plan = Plan(
        plan_id=f"plan_{uuid.uuid4().hex[:12]}",
        session_id=plan.session_id,
        project_id=plan.project_id,
        status=PlanStatus.PENDING_APPROVAL,
        is_fallback=new_plan_result.is_fallback,
        intent_analysis_type=intent.analysis_type,
        intent_complexity=intent.complexity,
        original_intent=intent_data,
        plan_result=new_plan_result,
        task_tree=new_task_tree,
        working_memory=plan.working_memory,
        parent_plan_id=plan.plan_id,
        version=plan.version + 1,
    )
    await plan_store.create(new_plan)
    record_plan_strategy_switch(
        plan.plan_result.strategy_name,
        new_plan_result.strategy_name,
    )

    return PlanApproveResponse(
        plan_id=new_plan.plan_id,
        status=new_plan.status,
        new_plan_id=new_plan.plan_id,
    )
