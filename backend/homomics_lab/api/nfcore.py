from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pathlib import Path

from homomics_lab.config import settings
from homomics_lab.nfcore_integration import get_nfcore_manager
from homomics_lab.nfcore_results import NFCoreResultIngester
from homomics_lab.nfcore_schema import form_to_dict, parse_schema, validate_params
from homomics_lab.workspace.manager import WorkspaceManager

router = APIRouter()


class NFCorePipelineResponse(BaseModel):
    name: str
    description: str
    topics: List[str]
    stars: int
    default_branch: str
    github_url: str
    latest_release: Optional[str] = None


class NFCoreRunRequest(BaseModel):
    pipeline: str
    version: Optional[str] = None
    params: Dict[str, Any] = {}
    profiles: Optional[List[str]] = None


@router.get("/pipelines", response_model=List[NFCorePipelineResponse])
async def list_nfcore_pipelines(
    request: Request,
    cached_only: bool = False,
):
    """List available nf-core pipelines.

    Args:
        cached_only: Only return pipelines already downloaded locally.
    """
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    try:
        pipelines = get_nfcore_manager().list_pipelines(use_cache=cached_only)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [
        NFCorePipelineResponse(
            name=p.name,
            description=p.description,
            topics=p.topics,
            stars=p.stars,
            default_branch=p.default_branch,
            github_url=p.github_url,
            latest_release=p.latest_release,
        )
        for p in pipelines
    ]


@router.post("/download/{pipeline}")
async def download_nfcore_pipeline(
    pipeline: str,
    version: Optional[str] = None,
):
    """Download/cache an nf-core pipeline."""
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    try:
        path = get_nfcore_manager().download_pipeline(pipeline, version)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"pipeline": pipeline, "version": version, "path": str(path)}


@router.post("/run")
async def run_nfcore_pipeline(
    request: NFCoreRunRequest,
):
    """Prepare an nf-core pipeline run command.

    The actual execution is delegated to the existing Nextflow/HPC runtime.
    """
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    try:
        result = get_nfcore_manager().run_pipeline(
            request.pipeline,
            params=request.params,
            version=request.version,
            profiles=request.profiles or settings.nfcore_default_profiles,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result


@router.get("/suggest")
async def suggest_nfcore_pipeline(
    intent: str,
):
    """Suggest an nf-core pipeline for a given analysis intent."""
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    suggestion = get_nfcore_manager().suggest_pipeline(intent)
    if suggestion is None:
        return {"suggestion": None, "message": "No curated nf-core pipeline mapping for this intent"}
    return {"suggestion": suggestion}


@router.get("/releases/{pipeline}")
async def list_nfcore_releases(
    pipeline: str,
):
    """List available releases/tags for an nf-core pipeline."""
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    try:
        releases = get_nfcore_manager().list_releases(pipeline)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"pipeline": pipeline, "releases": releases}


@router.get("/schema/{pipeline}")
async def get_nfcore_schema(
    pipeline: str,
    version: Optional[str] = None,
):
    """Return the parameter schema for an nf-core pipeline as a user-friendly form."""
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    try:
        manager = get_nfcore_manager()
        schema = manager.load_schema(pipeline, version)
        form = parse_schema(schema, pipeline_name=pipeline, version=version)
        return form_to_dict(form)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class ValidateParamsRequest(BaseModel):
    pipeline: str
    version: Optional[str] = None
    params: Dict[str, Any] = {}


@router.post("/validate")
async def validate_nfcore_params(
    request: ValidateParamsRequest,
):
    """Validate user-provided params against a pipeline schema."""
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    try:
        manager = get_nfcore_manager()
        schema = manager.load_schema(request.pipeline, request.version)
        errors = validate_params(schema, request.params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return {"valid": True}


@router.get("/profiles")
async def detect_nfcore_profiles():
    """Detect available container/conda profiles on the host."""
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    available, recommended = get_nfcore_manager().detect_profiles()
    return {
        "available": available,
        "recommended": recommended,
        "default": settings.nfcore_default_profiles,
    }


class IngestResultsRequest(BaseModel):
    project_id: str
    output_dir: str
    task_id: str
    source_task: Optional[str] = None


@router.post("/ingest")
async def ingest_nfcore_results(request: IngestResultsRequest):
    """Scan an nf-core output directory and register artifacts in a workspace."""
    if not settings.nfcore_enabled:
        raise HTTPException(status_code=404, detail="nf-core integration is disabled")

    output_dir = Path(request.output_dir)
    if not output_dir.exists():
        raise HTTPException(status_code=400, detail=f"Output directory not found: {output_dir}")

    workspace = WorkspaceManager(
        base_dir=settings.data_dir,
        project_id=request.project_id,
    )
    ingester = NFCoreResultIngester(workspace)
    artifacts = ingester.ingest(
        output_dir=output_dir,
        task_id=request.task_id,
        source_task=request.source_task,
    )
    summary = ingester.ingest_multiqc_summary(output_dir)
    return {
        "project_id": request.project_id,
        "output_dir": str(output_dir),
        "task_id": request.task_id,
        "artifacts": artifacts,
        "multiqc_summary": summary,
    }
