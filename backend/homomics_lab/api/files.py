import base64
import mimetypes
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from homomics_lab.config import settings
from homomics_lab.projects.permissions import require_project_read, require_project_write
from homomics_lab.security import validate_project_id, sanitize_filename, safe_path
from homomics_lab.storage import get_storage_backend, StorageBackend
from homomics_lab.workspace.manager import WorkspaceManager

router = APIRouter()

# Per-file upload cap (formerly HOMOMICS_MAX_UPLOAD_FILE_BYTES; default kept).
MAX_UPLOAD_FILE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB


class FileListEntry(BaseModel):
    name: str
    type: str
    path: str
    size: Optional[int]
    modified_at: float


class FileListResponse(BaseModel):
    project_id: str
    path: str
    entries: List[FileListEntry]


class FileReadResponse(BaseModel):
    project_id: str
    path: str
    mime_type: str
    size: int
    encoding: str
    content: str


class FileUploadResponse(BaseModel):
    filename: str
    path: str
    storage_uri: str
    size: int
    project_id: str


_MAX_READ_BYTES = 5 * 1024 * 1024  # 5 MB preview limit
_MAX_PREVIEW_BYTES = 100 * 1024 * 1024  # 100 MB preview limit for full streams
_CHUNK_SIZE = 1024 * 1024  # 1 MB upload chunk size
_STREAM_CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunks


def _project_root(project_id: str) -> Path:
    # Use the unified project workspace as the file-browser root so outputs,
    # logs, and data live under one tree instead of being scattered under raw/.
    return (settings.data_dir / "workspaces" / project_id).resolve()


def _range_stream(path: Path, start: int, end: int, chunk_size: int = _STREAM_CHUNK_SIZE):
    """Yield bytes from ``start`` to ``end`` (inclusive) without loading the whole file."""
    remaining = end - start + 1
    with open(path, "rb") as f:
        f.seek(start)
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            yield chunk
            remaining -= len(chunk)


def _full_stream(path: Path, chunk_size: int = _STREAM_CHUNK_SIZE):
    """Yield the entire file in chunks."""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def _parse_range(range_header: str, file_size: int) -> Optional[tuple[int, int]]:
    """Parse a single ``bytes=start-end`` Range header.

    Returns ``(start, end)`` inclusive, or ``None`` if the range is unsatisfiable
    or uses syntax we do not support (e.g. multiple ranges).
    """
    if not range_header.startswith("bytes="):
        return None
    spec = range_header[len("bytes="):].strip()
    if "," in spec:
        # Multiple ranges are not implemented; let the client retry without Range.
        return None
    if "-" not in spec:
        return None
    start_str, end_str = spec.split("-", 1)
    try:
        if start_str == "":
            # Suffix range: bytes=-500 means last 500 bytes.
            suffix = int(end_str)
            if suffix <= 0:
                return None
            start = max(0, file_size - suffix)
            end = file_size - 1
        else:
            start = int(start_str)
            if end_str == "":
                end = file_size - 1
            else:
                end = int(end_str)
    except ValueError:
        return None

    if start < 0 or start >= file_size or end < start:
        return None
    end = min(end, file_size - 1)
    return start, end


@router.get("/list", dependencies=[Depends(require_project_read)], response_model=FileListResponse)
async def list_files(project_id: str, path: str = ""):
    """List files and directories under a project workspace path."""
    try:
        project_id = validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    root = _project_root(project_id)
    root.mkdir(parents=True, exist_ok=True)

    try:
        target = root if path.strip() == "" else safe_path(path, root=root, must_exist=True)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries = []
    for entry in target.iterdir():
        try:
            rel = str(entry.relative_to(root))
        except ValueError:
            rel = entry.name
        stat = entry.stat()
        entries.append(
            {
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "path": rel,
                "size": stat.st_size if entry.is_file() else None,
                "modified_at": stat.st_mtime,
            }
        )

    # Directories first, then alphabetical.
    entries.sort(key=lambda e: (0 if e["type"] == "directory" else 1, e["name"].lower()))
    return {"project_id": project_id, "path": path, "entries": entries}


@router.get("/read", dependencies=[Depends(require_project_read)], response_model=FileReadResponse)
async def read_file(project_id: str, path: str):
    """Read the contents of a project file as text or base64."""
    try:
        project_id = validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    root = _project_root(project_id)

    try:
        target = safe_path(path, root=root, must_exist=True)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    size = target.stat().st_size
    if size > _MAX_READ_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds preview size limit of {_MAX_READ_BYTES} bytes",
        )

    mime_type, _ = mimetypes.guess_type(target.name)
    mime_type = mime_type or "application/octet-stream"
    text_mime_types = {
        "application/json",
        "application/yaml",
        "application/x-yaml",
        "application/javascript",
        "application/xml",
        "application/x-sh",
    }

    if mime_type.startswith("text/") or mime_type in text_mime_types:
        content = target.read_text(encoding="utf-8", errors="replace")
        return {
            "project_id": project_id,
            "path": path,
            "mime_type": mime_type,
            "size": size,
            "encoding": "utf-8",
            "content": content,
        }

    content = base64.b64encode(target.read_bytes()).decode("ascii")
    return {
        "project_id": project_id,
        "path": path,
        "mime_type": mime_type,
        "size": size,
        "encoding": "base64",
        "content": content,
    }


@router.get("/preview", dependencies=[Depends(require_project_read)])
async def preview_file(request: Request, project_id: str, path: str):
    """Stream a project file with optional HTTP Range support.

    For requests without a ``Range`` header the full file is streamed up to
    ``_MAX_PREVIEW_BYTES``. For ``bytes=start-end`` Range requests a ``206 Partial
    Content`` response is returned with the correct ``Content-Range`` header.
    """
    try:
        project_id = validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    root = _project_root(project_id)

    try:
        target = safe_path(path, root=root, must_exist=True)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    size = target.stat().st_size
    mime_type, _ = mimetypes.guess_type(target.name)
    mime_type = mime_type or "application/octet-stream"
    common_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": mime_type,
    }

    range_header = request.headers.get("range")
    if range_header:
        parsed = _parse_range(range_header, size)
        if parsed is None:
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{size}"},
            )
        start, end = parsed
        content_length = end - start + 1
        headers = {
            **common_headers,
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(content_length),
        }
        return StreamingResponse(
            _range_stream(target, start, end),
            status_code=206,
            headers=headers,
        )

    if size > _MAX_PREVIEW_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds preview size limit of {_MAX_PREVIEW_BYTES} bytes",
        )

    return StreamingResponse(
        _full_stream(target),
        headers={
            **common_headers,
            "Content-Length": str(size),
        },
    )


@router.post("/upload", dependencies=[Depends(require_project_write)], response_model=FileUploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    project_id: str = "default",
):
    # Validate identifiers before consuming the stream so malformed requests
    # fail fast without touching disk.
    try:
        project_id = validate_project_id(project_id)
        filename = sanitize_filename(file.filename or "upload.bin")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    max_bytes = MAX_UPLOAD_FILE_BYTES
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            total_size = 0
            while chunk := await file.read(_CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum upload size of {max_bytes} bytes",
                    )
                tmp.write(chunk)

        # Stream the staged temp file into the configured object store.
        backend = get_storage_backend()
        key = StorageBackend.make_key(project_id, "uploads", filename)
        with open(tmp_path, "rb") as src:
            uri = backend.put(key, src)

        # Keep a local project copy for backward compatibility / fast access.
        project_dir = settings.data_dir / "raw" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        file_path = project_dir / filename
        shutil.copy2(tmp_path, file_path)

        # Mirror into the project's workspace data directory so skills can find
        # the file when creating a session.
        ws = WorkspaceManager(settings.data_dir, project_id)
        ws_data_path = ws.get_data_path(filename)
        ws_data_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp_path, ws_data_path)

        return {
            "filename": filename,
            "path": str(file_path),
            "storage_uri": uri,
            "size": total_size,
            "project_id": project_id,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/{project_id}/{path:path}", dependencies=[Depends(require_project_read)])
async def serve_project_file(project_id: str, path: str):
    """Serve a file from a project's workspace for previews/downloads."""
    from homomics_lab.security import validate_project_id, safe_path

    try:
        project_id = validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    root = (settings.data_dir / "workspaces" / project_id).resolve()
    try:
        target = safe_path(path, root=root, must_exist=True)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    mime_type, _ = mimetypes.guess_type(target.name)
    mime_type = mime_type or "application/octet-stream"
    return FileResponse(path=target, media_type=mime_type, filename=target.name)
