"""API endpoints for the domain template marketplace."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from homomics_lab.domain.marketplace import DomainMarketplace, DomainMarketplaceError

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_marketplace(request: Request) -> DomainMarketplace:
    marketplace = getattr(request.app.state, "domain_marketplace", None)
    if marketplace is None:
        raise HTTPException(
            status_code=503,
            detail="Domain marketplace is not initialized. The application may still be starting up.",
        )
    return marketplace


class ImportDomainRequest(BaseModel):
    source: str
    target_name: Optional[str] = None


class ImportTemplatesRequest(BaseModel):
    domain_id: str
    templates: Dict[str, Any]


class DomainListItem(BaseModel):
    domain_id: str
    name: str
    description: str
    version: str
    path: str
    source: str


class DomainReferenceResponse(BaseModel):
    domain_id: str
    path: str


class DomainPreviewResponse(BaseModel):
    domain_id: str
    name: str
    description: str
    version: str
    author: str
    orchestrator_skills: List[Any]
    phases: List[Any]
    phase_transitions: List[Any]
    intents: List[Any]
    skills: List[Any]
    roles: List[Any]
    sops: List[Any]
    code_templates: Dict[str, Any]


class DomainExportResponse(BaseModel):
    domain_id: str
    zip_path: str


@router.get("/", response_model=List[DomainListItem])
async def list_domains(request: Request):
    """List available domain templates."""
    marketplace = _get_marketplace(request)
    domains = marketplace.list_domains()
    return [
        {
            "domain_id": d.domain_id,
            "name": d.name,
            "description": d.description,
            "version": d.version,
            "path": d.path,
            "source": d.source,
        }
        for d in domains
    ]


@router.post("/import", response_model=DomainReferenceResponse)
async def import_domain(request: Request, body: ImportDomainRequest):
    """Import a domain template from a local path, zip archive, or git URL."""
    marketplace = _get_marketplace(request)
    try:
        target_dir = marketplace.import_domain(body.source, target_name=body.target_name)
    except DomainMarketplaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Domain import failed (source=%s)", body.source)
        raise HTTPException(status_code=500, detail="Internal error") from exc
    return {"domain_id": target_dir.name, "path": str(target_dir)}


@router.post("/import-zip", response_model=DomainReferenceResponse)
async def import_domain_zip(
    request: Request,
    file: UploadFile = File(...),
    target_name: Optional[str] = Form(None),
):
    """Upload and import a domain template zip archive."""
    import tempfile

    marketplace = _get_marketplace(request)
    suffix = Path(file.filename or "domain.zip").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        target_dir = marketplace.import_domain(tmp_path, target_name=target_name)
    except DomainMarketplaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Domain zip import failed (filename=%s)", file.filename)
        raise HTTPException(status_code=500, detail="Internal error") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"domain_id": target_dir.name, "path": str(target_dir)}


@router.post("/import-templates", response_model=DomainReferenceResponse)
async def import_templates(request: Request, body: ImportTemplatesRequest):
    """Import code templates into an existing domain."""
    marketplace = _get_marketplace(request)
    try:
        domain_dir = marketplace.import_code_templates(body.domain_id, body.templates)
    except DomainMarketplaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Domain template import failed (domain_id=%s)", body.domain_id)
        raise HTTPException(status_code=500, detail="Internal error") from exc
    return {"domain_id": body.domain_id, "path": str(domain_dir)}


@router.get("/{domain_id}/preview", response_model=DomainPreviewResponse)
async def preview_domain(domain_id: str, request: Request):
    """Return detailed preview data for a domain template."""
    marketplace = _get_marketplace(request)
    source_dir = marketplace._find_domain_dir(domain_id)
    if source_dir is None:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    domain_yaml = source_dir / "domain.yaml"
    if not domain_yaml.exists():
        raise HTTPException(status_code=404, detail="domain.yaml not found")

    try:
        data: Dict[str, Any] = yaml.safe_load(domain_yaml.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read domain: {exc}") from exc
    except Exception as exc:
        logger.exception("Domain preview failed (domain_id=%s)", domain_id)
        raise HTTPException(status_code=500, detail="Internal error") from exc

    return {
        "domain_id": domain_id,
        "name": data.get("display_name") or data.get("domain", domain_id),
        "description": data.get("description", ""),
        "version": data.get("version", "1.0.0"),
        "author": data.get("author", ""),
        "orchestrator_skills": data.get("orchestrator_skills", []),
        "phases": data.get("phases", []),
        "phase_transitions": data.get("phase_transitions", []),
        "intents": data.get("intents", []),
        "skills": data.get("skills", []),
        "roles": data.get("roles", []),
        "sops": data.get("sops", []),
        "code_templates": data.get("code_templates", {}),
    }


@router.post("/{domain_id}/export", response_model=DomainExportResponse)
async def export_domain(domain_id: str, request: Request):
    """Export a domain template as a zip archive.

    Returns the path to the created zip file. In production this should stream
    the file to the client instead of returning a server path.
    """
    import tempfile

    marketplace = _get_marketplace(request)
    try:
        output_path = marketplace.export_domain(
            domain_id,
            output_path=Path(tempfile.gettempdir()) / f"{domain_id}_domain.zip",
        )
    except DomainMarketplaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Domain export failed (domain_id=%s)", domain_id)
        raise HTTPException(status_code=500, detail="Internal error") from exc
    return {"domain_id": domain_id, "zip_path": str(output_path)}
