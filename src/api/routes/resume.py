# File: src/api/routes/resume.py
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_db

router = APIRouter()


class RollbackRequest(BaseModel):
    """Request payload for rolling a resume back to a previous version."""

    user_id: int = Field(..., ge=1)
    resume_version_id: int = Field(..., ge=1)


@router.post("/upload")
async def upload_resume(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Upload a resume file for parsing and storage."""

    _ = db
    return {"filename": file.filename, "status": "accepted", "resume_version_id": None}


@router.post("/rollback")
async def rollback_resume(
    payload: RollbackRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Rollback a user's active resume to a prior version."""

    _ = db
    return {
        "status": "rollback_queued",
        "user_id": payload.user_id,
        "resume_version_id": payload.resume_version_id,
    }
