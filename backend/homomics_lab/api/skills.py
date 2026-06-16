from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from homomics_lab.skills.promotion import TransientSkillPromoter
from homomics_lab.skills.skill_store import SkillStore
from homomics_lab.tools.approval import get_default_approval_store

router = APIRouter()


def _get_store(request: Request) -> SkillStore:
    store = request.app.state.skill_store
    if store is None:
        raise HTTPException(status_code=500, detail="SkillStore not initialized")
    return store


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
    namespace: str = "default"
    enabled: bool = True
    trusted: bool = False


class ImportSkillRequest(BaseModel):
    source: str
    namespace: Optional[str] = "default"
    skill_id: Optional[str] = None
    enable: bool = True


class ImportSkillResponse(BaseModel):
    skill_id: str
    name: str
    version: str
    namespace: str
    enabled: bool


class ValidationResponse(BaseModel):
    valid: bool
    errors: List[str]
    warnings: List[str]


class TestResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: Optional[int]
    tests_run: int
    tests_passed: int


class TrustSkillRequest(BaseModel):
    trusted: bool = True


class PromoteSkillRequest(BaseModel):
    source_dir: str
    skill_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: str = "generated"
    namespace: str = "default"
    trusted: bool = False


class LockResponse(BaseModel):
    project_id: str
    locked_at: str
    skills: Dict[str, str]



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


@router.get("/tools/pending")
async def list_pending_tool_approvals():
    """List high-risk tool calls awaiting user approval."""
    store = get_default_approval_store()
    return [
        {
            "call_id": r.call_id,
            "tool_name": r.tool_name,
            "arguments": r.arguments,
            "risk_level": r.risk_level,
        }
        for r in store.list_pending()
    ]


@router.post("/approve-tool/{call_id}")
async def approve_tool_call(call_id: str):
    """Approve a pending high-risk tool call."""
    store = get_default_approval_store()
    if not store.approve(call_id):
        raise HTTPException(status_code=404, detail=f"Approval request '{call_id}' not found")
    return {"call_id": call_id, "approved": True}


@router.post("/reject-tool/{call_id}")
async def reject_tool_call(call_id: str):
    """Reject a pending high-risk tool call."""
    store = get_default_approval_store()
    if not store.reject(call_id):
        raise HTTPException(status_code=404, detail=f"Approval request '{call_id}' not found")
    return {"call_id": call_id, "approved": False}


@router.get("/{skill_id}", response_model=SkillDetail)
async def get_skill(request: Request, skill_id: str):
    """Get detailed information about a specific skill."""
    executor = request.app.state.skill_executor
    skill = executor.registry.get(skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    # Progressive disclosure: viewing a skill detail is an activation event.
    executor.registry.activate(skill_id)

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
        trusted=skill.metadata.get("trusted", False),
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


@router.post("/import", response_model=ImportSkillResponse)
async def import_skill(request: Request, body: ImportSkillRequest):
    """Import a skill from a local path, git URL, or zip archive."""
    store = _get_store(request)
    try:
        skill = store.import_skill(
            source=body.source,
            namespace=body.namespace,
            skill_id=body.skill_id,
            enable=body.enable,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ImportSkillResponse(
        skill_id=skill.id,
        name=skill.name,
        version=skill.version,
        namespace=skill.metadata.get("namespace", "default"),
        enabled=body.enable,
    )


@router.post("/{skill_id}/update", response_model=ImportSkillResponse)
async def update_skill(request: Request, skill_id: str, body: ImportSkillRequest):
    """Re-import a skill from a new source."""
    store = _get_store(request)
    try:
        skill = store.update_skill(
            skill_id=skill_id,
            source=body.source,
            namespace=body.namespace,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ImportSkillResponse(
        skill_id=skill.id,
        name=skill.name,
        version=skill.version,
        namespace=skill.metadata.get("namespace", "default"),
        enabled=True,
    )


@router.delete("/{skill_id}")
async def remove_skill(
    request: Request,
    skill_id: str,
    namespace: Optional[str] = "default",
):
    """Remove a skill from the store and runtime registry."""
    store = _get_store(request)
    try:
        store.remove_skill(skill_id, namespace=namespace)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"skill_id": skill_id, "namespace": namespace, "removed": True}


@router.post("/{skill_id}/enable")
async def enable_skill(
    request: Request,
    skill_id: str,
    namespace: Optional[str] = "default",
):
    """Enable a disabled skill."""
    store = _get_store(request)
    try:
        skill = store.enable_skill(skill_id, namespace=namespace)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"skill_id": skill.id, "namespace": namespace, "enabled": True}


@router.post("/{skill_id}/disable")
async def disable_skill(
    request: Request,
    skill_id: str,
    namespace: Optional[str] = "default",
):
    """Disable a skill without removing it."""
    store = _get_store(request)
    try:
        store.disable_skill(skill_id, namespace=namespace)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"skill_id": skill_id, "namespace": namespace, "enabled": False}


@router.post("/{skill_id}/validate", response_model=ValidationResponse)
async def validate_skill(
    request: Request,
    skill_id: str,
    namespace: Optional[str] = "default",
):
    """Validate the skill directory structure."""
    store = _get_store(request)
    meta = store.get_meta(skill_id, namespace=namespace)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    report = SkillStore.validate_skill(Path(meta["source_dir"]))
    return ValidationResponse(
        valid=report.valid,
        errors=report.errors,
        warnings=report.warnings,
    )


@router.post("/{skill_id}/test", response_model=TestResponse)
async def test_skill(
    request: Request,
    skill_id: str,
    namespace: Optional[str] = "default",
):
    """Run the skill's built-in tests."""
    store = _get_store(request)
    try:
        report = store.run_tests(skill_id, namespace=namespace)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return TestResponse(
        success=report.success,
        stdout=report.stdout,
        stderr=report.stderr,
        exit_code=report.exit_code,
        tests_run=report.tests_run,
        tests_passed=report.tests_passed,
    )


@router.post("/promote")
async def promote_skill(request: Request, body: PromoteSkillRequest):
    """Promote a successful CodeAct run into a curated skill.

    The ``source_dir`` must contain ``__code_act_source__.py`` (saved by
    CodeAct) and optionally ``__skill_result__.json``. The generated skill
    package is imported into the skill store as an untrusted skill by default;
    use ``POST /skills/{id}/trust`` to mark it trusted after review.
    """
    store = _get_store(request)
    if not Path(body.source_dir).exists():
        raise HTTPException(status_code=400, detail=f"Source directory not found: {body.source_dir}")

    try:
        promoter = TransientSkillPromoter(skill_registry=store.registry)
        package_dir = promoter.create_package(
            source_dir=Path(body.source_dir),
            skill_id=body.skill_id,
            name=body.name,
            description=body.description,
            category=body.category,
        )
        skill = store.import_skill(
            source=str(package_dir),
            namespace=body.namespace,
            skill_id=body.skill_id,
            enable=True,
        )
        # Force untrusted unless explicitly requested and the user has permission.
        if not body.trusted:
            skill.metadata["trusted"] = False
            store.trust_skill(skill.id, trusted=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "skill_id": skill.id,
        "name": skill.name,
        "namespace": skill.metadata.get("namespace", "default"),
        "source_dir": str(package_dir),
        "trusted": skill.metadata.get("trusted", False),
    }


@router.post("/{skill_id}/trust")
async def trust_skill(
    request: Request,
    skill_id: str,
    body: TrustSkillRequest,
):
    """Mark a skill as trusted or untrusted.

    Only trusted external/community skills are allowed to execute scripts
    and shell commands.
    """
    store = _get_store(request)
    try:
        skill = store.trust_skill(skill_id, trusted=body.trusted)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {
        "skill_id": skill.id,
        "namespace": skill.metadata.get("namespace", "default"),
        "trusted": skill.metadata.get("trusted", False),
    }


@router.post("/lock", response_model=LockResponse)
async def lock_skills(request: Request, project_id: str):
    """Create a version lock for currently enabled skills."""
    store = _get_store(request)
    lock = store.lock_versions(project_id)
    return LockResponse(
        project_id=lock.project_id,
        locked_at=lock.locked_at,
        skills=lock.skills,
    )
