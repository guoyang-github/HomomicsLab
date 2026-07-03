from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from homomics_lab.api.auth import require_admin, require_auth
from homomics_lab.api.responses import MessageResponse
from homomics_lab.security import PathSecurityError, safe_extractall
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
    version: str
    category: str
    runtime_type: str
    primary_tool: str
    source: str = "builtin"
    namespace: str = "default"
    enabled: bool = True


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


class ImportDirectoryRequest(BaseModel):
    source_dir: Optional[str] = None
    namespace: Optional[str] = "user"


class ImportDirectoryResponse(BaseModel):
    imported: List[ImportSkillResponse]
    failed: List[Dict[str, str]]


class ImportZipResponse(BaseModel):
    imported: List[ImportSkillResponse]
    failed: List[Dict[str, str]]


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


class PendingToolApproval(BaseModel):
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    risk_level: str


class ToolApprovalResponse(BaseModel):
    call_id: str
    approved: bool


class SkillMetricsResponse(BaseModel):
    skill_id: str
    total_executions: int
    success_rate: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    avg_output_size: float
    avg_cpu_percent: Optional[float]
    avg_memory_mb: Optional[float]
    avg_gpu_percent: Optional[float]
    total_cost_usd: float


class SkillExecutionRecord(BaseModel):
    skill_id: str
    timestamp: str
    duration_ms: float
    success: bool
    output_size: int
    executor_type: str
    error_message: Optional[str]


class TopSkillMetric(BaseModel):
    skill_id: str
    total_executions: int
    success_rate: float
    avg_duration_ms: float
    total_cost_usd: float


class SkillToggleResponse(BaseModel):
    skill_id: str
    namespace: str
    enabled: bool


class RemoveSkillResponse(BaseModel):
    skill_id: str
    namespace: str
    removed: bool


class PromoteSkillResponse(BaseModel):
    skill_id: str
    name: str
    namespace: str
    source_dir: str
    trusted: bool


class TrustSkillResponse(BaseModel):
    skill_id: str
    namespace: str
    trusted: bool


@router.get(
    "/", response_model=List[SkillSummary], dependencies=[Depends(require_auth)]
)
async def list_skills(request: Request):
    """List all registered skills."""
    executor = request.app.state.skill_executor
    skills = executor.registry.list_all()

    return [
        SkillSummary(
            id=s.id,
            name=s.name,
            description=s.description,
            version=s.version,
            category=s.category,
            runtime_type=s.runtime.type,
            primary_tool=s.metadata.get("primary_tool", ""),
            source=s.metadata.get("source", "builtin"),
            namespace=s.metadata.get("namespace", "default"),
            enabled=s.metadata.get("enabled", True),
        )
        for s in skills
    ]


@router.get(
    "/search", response_model=List[SkillSummary], dependencies=[Depends(require_auth)]
)
async def search_skills(request: Request, q: str):
    """Search skills by keyword."""
    executor = request.app.state.skill_executor
    skills = executor.registry.search(q)

    return [
        SkillSummary(
            id=s.id,
            name=s.name,
            description=s.description,
            version=s.version,
            category=s.category,
            runtime_type=s.runtime.type,
            primary_tool=s.metadata.get("primary_tool", ""),
            source=s.metadata.get("source", "builtin"),
            namespace=s.metadata.get("namespace", "default"),
            enabled=s.metadata.get("enabled", True),
        )
        for s in skills
    ]


@router.get(
    "/tools/pending",
    response_model=List[PendingToolApproval],
    dependencies=[Depends(require_auth)],
)
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


@router.post(
    "/approve-tool/{call_id}",
    response_model=ToolApprovalResponse,
    dependencies=[Depends(require_admin)],
)
async def approve_tool_call(call_id: str):
    """Approve a pending high-risk tool call."""
    store = get_default_approval_store()
    if not store.approve(call_id):
        raise HTTPException(
            status_code=404, detail=f"Approval request '{call_id}' not found"
        )
    return {"call_id": call_id, "approved": True}


@router.post(
    "/reject-tool/{call_id}",
    response_model=ToolApprovalResponse,
    dependencies=[Depends(require_admin)],
)
async def reject_tool_call(call_id: str):
    """Reject a pending high-risk tool call."""
    store = get_default_approval_store()
    if not store.reject(call_id):
        raise HTTPException(
            status_code=404, detail=f"Approval request '{call_id}' not found"
        )
    return {"call_id": call_id, "approved": False}


@router.get(
    "/{skill_id}", response_model=SkillDetail, dependencies=[Depends(require_auth)]
)
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


@router.get(
    "/{skill_id}/metrics",
    response_model=Union[SkillMetricsResponse, MessageResponse],
    dependencies=[Depends(require_auth)],
)
async def get_skill_metrics(request: Request, skill_id: str):
    """Get performance metrics for a skill."""
    executor = request.app.state.skill_executor
    skill = executor.registry.get(skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    if executor.tracker is None:
        return {"skill_id": skill_id, "message": "Metrics tracking not enabled"}

    return executor.tracker.get_stats(skill_id)


@router.get(
    "/{skill_id}/executions",
    response_model=List[SkillExecutionRecord],
    dependencies=[Depends(require_auth)],
)
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


@router.get(
    "/metrics/top",
    response_model=List[TopSkillMetric],
    dependencies=[Depends(require_auth)],
)
async def get_top_skills(request: Request, limit: int = 10):
    """Get top skills by execution count."""
    executor = request.app.state.skill_executor

    if executor.tracker is None:
        return []

    return executor.tracker.get_top_skills(limit=limit)


def _import_directory(
    store: SkillStore, source_dir: Path, namespace: str
) -> tuple[List[ImportSkillResponse], List[Dict[str, str]]]:
    """Import every skill subdirectory under ``source_dir`` into the store."""
    imported: List[ImportSkillResponse] = []
    failed: List[Dict[str, str]] = []
    for skill_path in sorted(source_dir.iterdir()):
        if not skill_path.is_dir():
            continue
        if not (skill_path / "SKILL.md").exists():
            continue
        try:
            skill = store.import_skill(
                source=str(skill_path),
                namespace=namespace,
                enable=True,
            )
            imported.append(
                ImportSkillResponse(
                    skill_id=skill.id,
                    name=skill.name,
                    version=skill.version,
                    namespace=skill.metadata.get("namespace", namespace),
                    enabled=True,
                )
            )
        except Exception as exc:
            failed.append({"path": str(skill_path), "error": str(exc)})
    return imported, failed


@router.post(
    "/import", response_model=ImportSkillResponse, dependencies=[Depends(require_admin)]
)
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


@router.post(
    "/import-directory",
    response_model=ImportDirectoryResponse,
    dependencies=[Depends(require_admin)],
)
async def import_skill_directory(request: Request, body: ImportDirectoryRequest):
    """Bulk import all skill subdirectories under a directory (defaults to settings.skills_dir)."""
    from homomics_lab.config import settings

    store = _get_store(request)
    source_dir = Path(
        body.source_dir or str(settings.skills_dir)
    ).expanduser().resolve()
    if not source_dir.exists():
        raise HTTPException(
            status_code=400, detail=f"Directory not found: {source_dir}"
        )

    imported, failed = _import_directory(store, source_dir, body.namespace or "user")
    return ImportDirectoryResponse(imported=imported, failed=failed)


@router.post(
    "/import-zip",
    response_model=ImportZipResponse,
    dependencies=[Depends(require_admin)],
)
async def import_skill_zip(
    request: Request,
    file: UploadFile = File(...),
    namespace: Optional[str] = "user",
):
    """Upload a zip archive containing skill directories and import them all."""
    store = _get_store(request)
    suffix = Path(file.filename or "skills.zip").suffix or ".zip"
    with tempfile.TemporaryDirectory(prefix="homomics_skill_zip_") as tmp:
        archive_path = Path(tmp) / f"upload{suffix}"
        archive_path.write_bytes(await file.read())

        extract_dir = Path(tmp) / "extracted"
        extract_dir.mkdir()
        import zipfile

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                safe_extractall(zf, extract_dir)
        except zipfile.BadZipFile as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid zip file: {exc}"
            ) from exc
        except PathSecurityError as exc:
            raise HTTPException(
                status_code=400, detail=f"Unsafe zip archive: {exc}"
            ) from exc

        # If the zip has a single top-level directory, drill into it.
        entries = [e for e in extract_dir.iterdir() if e.is_dir()]
        if len(entries) == 1 and not (entries[0] / "SKILL.md").exists():
            scan_dir = entries[0]
        else:
            scan_dir = extract_dir

        imported, failed = _import_directory(store, scan_dir, namespace or "user")
    return ImportZipResponse(imported=imported, failed=failed)


@router.post(
    "/{skill_id}/update",
    response_model=ImportSkillResponse,
    dependencies=[Depends(require_admin)],
)
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


@router.delete(
    "/{skill_id}",
    response_model=RemoveSkillResponse,
    dependencies=[Depends(require_admin)],
)
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


@router.post(
    "/{skill_id}/enable",
    response_model=SkillToggleResponse,
    dependencies=[Depends(require_admin)],
)
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


@router.post(
    "/{skill_id}/disable",
    response_model=SkillToggleResponse,
    dependencies=[Depends(require_admin)],
)
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


@router.post(
    "/{skill_id}/validate",
    response_model=ValidationResponse,
    dependencies=[Depends(require_admin)],
)
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


@router.post(
    "/{skill_id}/test",
    response_model=TestResponse,
    dependencies=[Depends(require_admin)],
)
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


@router.post(
    "/promote",
    response_model=PromoteSkillResponse,
    dependencies=[Depends(require_admin)],
)
async def promote_skill(request: Request, body: PromoteSkillRequest):
    """Promote a successful CodeAct run into a curated skill.

    The ``source_dir`` must contain ``__code_act_source__.py`` (saved by
    CodeAct) and optionally ``__skill_result__.json``. The generated skill
    package is imported into the skill store as an untrusted skill by default;
    use ``POST /skills/{id}/trust`` to mark it trusted after review.
    """
    store = _get_store(request)
    if not Path(body.source_dir).exists():
        raise HTTPException(
            status_code=400, detail=f"Source directory not found: {body.source_dir}"
        )

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


@router.post(
    "/{skill_id}/trust",
    response_model=TrustSkillResponse,
    dependencies=[Depends(require_admin)],
)
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


@router.post(
    "/lock", response_model=LockResponse, dependencies=[Depends(require_admin)]
)
async def lock_skills(request: Request, project_id: str):
    """Create a version lock for currently enabled skills."""
    store = _get_store(request)
    lock = store.lock_versions(project_id)
    return LockResponse(
        project_id=lock.project_id,
        locked_at=lock.locked_at,
        skills=lock.skills,
    )
