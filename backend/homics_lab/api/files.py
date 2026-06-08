from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from homics_lab.config import settings

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), project_id: str = "default"):
    project_dir = settings.data_dir / "raw" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    file_path = project_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    return {
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content),
    }
