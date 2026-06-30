"""API endpoints for knowledge ingestion and graph search."""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from homomics_lab.config import settings
from homomics_lab.knowledge.ingestion import CognifyOptions, KnowledgeIndex
from homomics_lab.knowledge.ingestion.models import IngestionResult
from homomics_lab.security import validate_project_id

router = APIRouter()

_SOURCE_TYPE_LITERAL = Literal["file", "url", "text"]


class IngestRequest(BaseModel):
    source_type: _SOURCE_TYPE_LITERAL
    source: str = Field(..., description="File path, URL, or inline text")
    project_id: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class IngestResponse(BaseModel):
    document_id: str
    chunk_count: int
    entity_count: int
    relation_count: int
    memory_id: Optional[str] = None
    data_source_id: Optional[str] = None
    already_processed: bool = False


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]


def _get_knowledge_index(request: Request) -> Optional[KnowledgeIndex]:
    return getattr(request.app.state, "knowledge_index", None)


def _result_to_response(result: IngestionResult) -> IngestResponse:
    return IngestResponse(
        document_id=result.document_id,
        chunk_count=len(result.chunk_ids),
        entity_count=len(result.entity_names),
        relation_count=result.relation_count,
        memory_id=result.memory_id,
        data_source_id=result.data_source_id,
        already_processed=result.already_processed,
    )


def _build_options(payload: Optional[Dict[str, Any]]) -> CognifyOptions:
    if not payload:
        return CognifyOptions()
    return CognifyOptions(
        skip_existing=payload.get("skip_existing", True),
        max_concurrent_extractions=payload.get("max_concurrent_extractions", 4),
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: Request, body: IngestRequest):
    """Ingest a file path, URL or inline text into the knowledge graph."""
    index = _get_knowledge_index(request)
    if index is None:
        raise HTTPException(status_code=503, detail="Knowledge index is not available")

    project_id = _validate_project(body.project_id)
    options = _build_options(body.options)

    try:
        if body.source_type == "file":
            path = _resolve_file_path(body.source, project_id)
            result = await index.ingest_file(path, project_id=project_id, options=options)
        elif body.source_type == "url":
            result = await index.ingest_url(body.source, project_id=project_id, options=options)
        else:
            result = await index.ingest_text(body.source, project_id=project_id, options=options)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _result_to_response(result)


@router.post("/ingest-upload", response_model=IngestResponse)
async def ingest_upload(
    request: Request,
    file: UploadFile = File(...),
    project_id: str = Form("default"),
    options: Optional[str] = Form(None),
):
    """Upload a file and ingest it into the knowledge graph."""
    index = _get_knowledge_index(request)
    if index is None:
        raise HTTPException(status_code=503, detail="Knowledge index is not available")

    project_id = _validate_project(project_id)
    content = await file.read()
    max_bytes = settings.max_upload_file_bytes
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size of {max_bytes} bytes",
        )

    project_dir = settings.data_dir / "raw" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    from homomics_lab.security import sanitize_filename

    filename = sanitize_filename(file.filename or "upload.bin")
    file_path = project_dir / filename
    file_path.write_bytes(content)

    parsed_options = _build_options(_parse_options_form(options))
    try:
        result = await index.ingest_file(file_path, project_id=project_id, options=parsed_options)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _result_to_response(result)


@router.post("/cognify-project")
async def cognify_project(request: Request, project_id: str):
    """Ingest all supported files in a project directory."""
    index = _get_knowledge_index(request)
    if index is None:
        raise HTTPException(status_code=503, detail="Knowledge index is not available")

    project_id = _validate_project(project_id)
    project_dir = settings.data_dir / "raw" / project_id
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    results: List[IngestionResult] = []
    errors: List[str] = []
    supported_extensions = {
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".pdf",
        ".docx",
        ".html",
        ".htm",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in supported_extensions:
            continue
        try:
            result = await index.ingest_file(path, project_id=project_id)
            results.append(result)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    return {
        "project_id": project_id,
        "processed": len(results),
        "errors": errors,
        "documents": [
            {
                "document_id": r.document_id,
                "source": r.source.source,
                "already_processed": r.already_processed,
            }
            for r in results
        ],
    }


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    q: str,
    project_id: Optional[str] = None,
    type: Literal["chunk", "entity"] = "chunk",
    top_k: int = 5,
):
    """Semantic search over ingested knowledge chunks."""
    index = _get_knowledge_index(request)
    if index is None:
        raise HTTPException(status_code=503, detail="Knowledge index is not available")

    if type != "chunk":
        raise HTTPException(status_code=400, detail="Only chunk search is implemented")

    try:
        results = await index.search_chunks(q, project_id=project_id, top_k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SearchResponse(results=results)


@router.get("/documents/{document_id}")
async def get_document(request: Request, document_id: str):
    """Return the graph context for a specific document."""
    index = _get_knowledge_index(request)
    if index is None:
        raise HTTPException(status_code=503, detail="Knowledge index is not available")

    return await index.get_document_graph(document_id)


def _validate_project(project_id: Optional[str]) -> str:
    try:
        return validate_project_id(project_id or "default")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_file_path(source: str, project_id: str) -> Path:
    path = Path(source)
    if not path.is_absolute():
        path = (settings.data_dir / "raw" / project_id / source).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path


def _parse_options_form(options: Optional[str]) -> Optional[Dict[str, Any]]:
    if not options:
        return None
    import json

    try:
        return json.loads(options)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid options JSON: {exc}") from exc
