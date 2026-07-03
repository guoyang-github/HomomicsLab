"""Result loading API for DataStore references.

When a skill returns a large object, the runtime stores it via ``DataStore``
and returns a ``ResultReference``.  This module provides the endpoint that
resolves such references back into data or file streams.
"""

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from homomics_lab.api.auth import require_auth
from homomics_lab.config import settings
from homomics_lab.data import DataStore, ResultReference

router = APIRouter(tags=["results"])


class LoadResultRequest(BaseModel):
    inline: bool = False
    data: Optional[Any] = None
    path: Optional[str] = None
    format: str = "json"
    size: int = 0
    metadata: Optional[dict] = None


class ResultPayloadResponse(BaseModel):
    data: Any
    format: str
    size: int


def _data_store(request: Request) -> DataStore:
    skill_executor = getattr(request.app.state, "skill_executor", None)
    if skill_executor is not None:
        return skill_executor.data_store
    return DataStore(settings.data_dir)


def _validate_path(data_store: DataStore, path: str) -> Path:
    """Ensure the requested path is inside the configured results directory."""
    target = Path(path).resolve()
    base = data_store.results_dir.resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid result path") from exc
    return target


@router.post(
    "/load",
    response_model=ResultPayloadResponse,
    dependencies=[Depends(require_auth)],
)
async def load_result(
    request: LoadResultRequest,
    http_request: Request,
):
    """Resolve a ``ResultReference`` into data or a downloadable file stream."""
    data_store = _data_store(http_request)

    ref = ResultReference(
        inline=request.inline,
        data=request.data,
        path=request.path,
        format=request.format,
        size=request.size,
        metadata=request.metadata,
    )

    if ref.inline:
        return ResultPayloadResponse(data=ref.data, format=ref.format, size=ref.size)

    if ref.path is None:
        raise HTTPException(status_code=400, detail="Reference path is required")

    target = _validate_path(data_store, ref.path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Result artifact not found")

    if ref.format in {"parquet", "h5ad", "zarr", "pickle"}:
        if ref.format == "pickle" and not settings.allow_pickle_serialization:
            raise HTTPException(
                status_code=403,
                detail="Pickle result loading is disabled",
            )
        media_types = {
            "parquet": "application/octet-stream",
            "h5ad": "application/octet-stream",
            "zarr": "application/zip",
            "pickle": "application/octet-stream",
        }
        return FileResponse(
            path=target,
            media_type=media_types.get(ref.format, "application/octet-stream"),
            filename=target.name,
        )

    # JSON and other inline-compatible formats are loaded and returned.
    try:
        data = data_store.load(ref)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load result: {exc}") from exc

    return ResultPayloadResponse(data=data, format=ref.format, size=ref.size)
