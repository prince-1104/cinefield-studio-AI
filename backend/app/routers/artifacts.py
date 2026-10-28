"""Artifact router to securely serve generated and uploaded media files."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{file_path:path}")
async def get_artifact(file_path: str) -> FileResponse:
    """Serve media files (video clips, images, audio, final ad) securely."""
    base_dir = Path(settings.ARTIFACT_DIR).resolve()
    requested_file = (base_dir / file_path).resolve()

    # Path traversal protection
    try:
        requested_file.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: path traversal not allowed",
        )

    if not requested_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact not found: {file_path}",
        )

    mime_type, _ = mimetypes.guess_type(str(requested_file))
    return FileResponse(
        path=str(requested_file),
        media_type=mime_type or "application/octet-stream",
    )

