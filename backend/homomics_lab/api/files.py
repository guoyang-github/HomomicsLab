import base64
import mimetypes
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from homomics_lab.config import settings
from homomics_lab.projects.permissions import require_project_read, require_project_write
from homomics_lab.security import validate_project_id, sanitize_filename, safe_path
from homomics_lab.storage import get_storage_backend, StorageBackend
from homomics_lab.workspace.manager import WorkspaceManager

router = APIRouter()


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


def _project_root(project_id: str) -> Path:
    return (settings.data_dir / "raw" / project_id).resolve()


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


@router.post("/upload", dependencies=[Depends(require_project_write)], response_model=FileUploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    project_id: str = "default",
):
    # Enforce per-file size limit.
    max_bytes = settings.max_upload_file_bytes
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size of {max_bytes} bytes",
        )

    try:
        project_id = validate_project_id(project_id)
        filename = sanitize_filename(file.filename or "upload.bin")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Store in configured backend (local or S3/MinIO).
    backend = get_storage_backend()
    key = StorageBackend.make_key(project_id, "uploads", filename)
    uri = backend.put(key, content)

    # Also keep a local workspace copy for backward compatibility / fast access.
    project_dir = settings.data_dir / "raw" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    file_path = project_dir / filename
    file_path.write_bytes(content)

    # Mirror into the project's workspace data directory so skills (e.g.
    # bio-statistics-visualization) can find the file when creating a session.
    ws = WorkspaceManager(settings.data_dir, project_id)
    ws_data_path = ws.get_data_path(filename)
    ws_data_path.parent.mkdir(parents=True, exist_ok=True)
    ws_data_path.write_bytes(content)

    return {
        "filename": filename,
        "path": str(file_path),
        "storage_uri": uri,
        "size": len(content),
        "project_id": project_id,
    }


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
