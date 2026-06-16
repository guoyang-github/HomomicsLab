"""API endpoints for the domain template marketplace."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from homomics_lab.domain.marketplace import DomainMarketplace

router = APIRouter()


def _get_marketplace(request: Request) -> DomainMarketplace:
    marketplace = getattr(request.app.state, "domain_marketplace", None)
    if marketplace is None:
        from homomics_lab.config import settings
        from homomics_lab.skills.registry import get_default_registry

        builtin = Path(__file__).parent.parent / "domains"
        marketplace_dir = settings.data_dir / "marketplace" / "domains"
        marketplace = DomainMarketplace(
            builtin_domains_dir=builtin,
            marketplace_dir=marketplace_dir,
            skill_registry=get_default_registry(),
        )
        request.app.state.domain_marketplace = marketplace
    return marketplace


class ImportDomainRequest(BaseModel):
    source: str
    target_name: Optional[str] = None


class ImportTemplatesRequest(BaseModel):
    domain_id: str
    templates: dict


@router.get("/")
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


@router.post("/import")
async def import_domain(request: Request, body: ImportDomainRequest):
    """Import a domain template from a local path, zip archive, or git URL."""
    marketplace = _get_marketplace(request)
    try:
        target_dir = marketplace.import_domain(body.source, target_name=body.target_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"domain_id": target_dir.name, "path": str(target_dir)}


@router.post("/import-zip")
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
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"domain_id": target_dir.name, "path": str(target_dir)}


@router.post("/import-templates")
async def import_templates(request: Request, body: ImportTemplatesRequest):
    """Import code templates into an existing domain."""
    marketplace = _get_marketplace(request)
    try:
        domain_dir = marketplace.import_code_templates(body.domain_id, body.templates)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"domain_id": body.domain_id, "path": str(domain_dir)}


@router.post("/{domain_id}/export")
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
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"domain_id": domain_id, "zip_path": str(output_path)}
