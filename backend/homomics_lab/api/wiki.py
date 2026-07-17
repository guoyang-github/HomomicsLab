"""API endpoints for the LLM Wiki document knowledge base."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from homomics_lab.api.auth import get_current_user
from homomics_lab.database.connection import get_async_session
from homomics_lab.knowledge.wiki import WikiEngine, WikiStore
from homomics_lab.knowledge.wiki.models import WikiPage, WikiQueryResult
from homomics_lab.projects.permissions import require_project_permission
from homomics_lab.security import validate_project_id

logger = logging.getLogger(__name__)

router = APIRouter()


class CreatePageRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1)


class UpdatePageRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class GeneratePagesRequest(BaseModel):
    document_id: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2048)
    top_k: int = 5


def _get_wiki_engine(request: Request) -> WikiEngine:
    """Return a WikiEngine bound to the app's knowledge index if available."""
    if not hasattr(request.app.state, "wiki_engine"):
        from homomics_lab.knowledge.ingestion.index import KnowledgeIndex

        knowledge_index = getattr(request.app.state, "knowledge_index", None)
        if knowledge_index is None:
            try:
                knowledge_index = KnowledgeIndex()
                request.app.state.knowledge_index = knowledge_index
            except Exception:
                knowledge_index = None
        request.app.state.wiki_engine = WikiEngine(
            store=WikiStore(),
            knowledge_index=knowledge_index,
        )
    return request.app.state.wiki_engine


@router.post("/pages", response_model=Dict[str, Any])
async def create_page(
    request: Request,
    body: CreatePageRequest,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Create a new manual wiki page."""
    validated = _validate_project(project_id)
    await require_project_permission(validated, "write", db, user_id)
    engine = _get_wiki_engine(request)
    page = await engine.create_manual_page(
        project_id=validated,
        title=body.title,
        content=body.content,
        created_by=user_id,
    )
    return _page_to_dict(page)


@router.get("/pages", response_model=List[Dict[str, Any]])
async def list_pages(
    request: Request,
    project_id: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """List wiki pages for a project."""
    validated = _validate_project(project_id)
    await require_project_permission(validated, "read", db, user_id)
    engine = _get_wiki_engine(request)
    pages = engine.store.list_pages(validated, query=q, limit=limit)
    return [_page_to_dict(p) for p in pages]


@router.get("/pages/{page_id}", response_model=Dict[str, Any])
async def get_page(
    request: Request,
    page_id: str,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Get a single wiki page."""
    validated = _validate_project(project_id)
    await require_project_permission(validated, "read", db, user_id)
    engine = _get_wiki_engine(request)
    page = engine.store.get_page(page_id)
    if page is None or page.project_id != validated:
        raise HTTPException(status_code=404, detail="Page not found")
    return _page_to_dict(page, store=engine.store, include_links=True)


@router.patch("/pages/{page_id}", response_model=Dict[str, Any])
async def update_page(
    request: Request,
    page_id: str,
    body: UpdatePageRequest,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Update a wiki page title/content."""
    validated = _validate_project(project_id)
    await require_project_permission(validated, "write", db, user_id)
    engine = _get_wiki_engine(request)
    page = engine.store.get_page(page_id)
    if page is None or page.project_id != validated:
        raise HTTPException(status_code=404, detail="Page not found")
    updated = engine.store.update_page(
        page_id,
        title=body.title,
        content=body.content,
        metadata={"last_editor": user_id},
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return _page_to_dict(updated)


@router.delete("/pages/{page_id}", response_model=Dict[str, bool])
async def delete_page(
    request: Request,
    page_id: str,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Delete a wiki page."""
    validated = _validate_project(project_id)
    await require_project_permission(validated, "write", db, user_id)
    engine = _get_wiki_engine(request)
    page = engine.store.get_page(page_id)
    if page is None or page.project_id != validated:
        raise HTTPException(status_code=404, detail="Page not found")
    engine.store.delete_page(page_id)
    return {"deleted": True}


@router.post("/pages/generate", response_model=List[Dict[str, Any]])
async def generate_pages(
    request: Request,
    body: GeneratePagesRequest,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Auto-generate wiki pages from an ingested document."""
    validated = _validate_project(project_id)
    await require_project_permission(validated, "write", db, user_id)
    engine = _get_wiki_engine(request)
    if engine.knowledge_index is None:
        raise HTTPException(status_code=503, detail="Knowledge index is not available")
    try:
        pages = await engine.generate_pages_from_document(
            body.document_id, project_id=validated
        )
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Wiki page generation failed (document_id=%s)", body.document_id)
        raise HTTPException(status_code=500, detail="Internal error") from exc
    return [_page_to_dict(p) for p in pages]


@router.post("/ask", response_model=Dict[str, Any])
async def ask_wiki(
    request: Request,
    body: AskRequest,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    user_id: str = Depends(get_current_user),
):
    """Ask a question over the project's wiki and ingested documents."""
    validated = _validate_project(project_id)
    await require_project_permission(validated, "read", db, user_id)
    engine = _get_wiki_engine(request)
    try:
        result = await engine.answer(body.question, project_id=validated, top_k=body.top_k)
    except Exception as exc:
        logger.exception("Wiki ask failed (project_id=%s)", validated)
        raise HTTPException(status_code=500, detail="Internal error") from exc
    return _result_to_dict(result)


def _validate_project(project_id: Optional[str]) -> str:
    return validate_project_id(project_id) if project_id else "default"


def _page_to_dict(
    page: WikiPage, store: Optional[WikiStore] = None, include_links: bool = False
) -> Dict[str, Any]:
    data = {
        "page_id": page.page_id,
        "project_id": page.project_id,
        "title": page.title,
        "content": page.content,
        "source_document_ids": page.source_document_ids,
        "source_chunk_ids": page.source_chunk_ids,
        "entity_types": page.entity_types,
        "created_at": page.created_at,
        "updated_at": page.updated_at,
        "created_by": page.created_by,
        "version": page.version,
        "metadata": page.metadata,
    }
    if include_links and store is not None:
        data["links"] = [
            {
                "source_id": link.source_id,
                "target_id": link.target_id,
                "relation": link.relation,
                "strength": link.strength,
            }
            for link in store.get_links(page.page_id, direction="both")
        ]
    return data


def _result_to_dict(result: WikiQueryResult) -> Dict[str, Any]:
    return {
        "answer": result.answer,
        "sources": result.sources,
        "suggested_pages": result.suggested_pages,
    }
