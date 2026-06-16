from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from homomics_lab.config import settings
from homomics_lab.security import validate_project_id, sanitize_filename
from homomics_lab.storage import get_storage_backend, StorageBackend

router = APIRouter()


@router.post("/upload")
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

    return {
        "filename": filename,
        "path": str(file_path),
        "storage_uri": uri,
        "size": len(content),
        "project_id": project_id,
    }
