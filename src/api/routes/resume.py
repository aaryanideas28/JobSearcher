# File: src/api/routes/resume.py
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import ResumeVersion, User
from src.api.dependencies import get_db
from src.utils.resume_parser import ResumeParser

router = APIRouter()
UPLOAD_DIR = Path("storage_workspace/uploads")


class RollbackRequest(BaseModel):
    """Request payload for rolling a resume back to a previous version."""

    user_id: int = Field(..., ge=1)
    resume_version_id: int = Field(..., ge=1)


class ResumeUploadRequest(BaseModel):
    """JSON payload for creating a resume version."""

    user_email: str = Field(..., min_length=3)
    full_name: str = Field(default="Candidate", min_length=1)
    resume_text: str = Field(..., min_length=1)
    version_label: str = Field(default="original", min_length=1, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/upload")
async def upload_resume(
    payload: ResumeUploadRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Persist a resume text upload as a versioned resume record."""

    user = db.query(User).filter(User.email == payload.user_email).one_or_none()
    if user is None:
        user = User(email=payload.user_email, full_name=payload.full_name)
        db.add(user)
        db.flush()

    resume_version = ResumeVersion(
        user_id=user.id,
        version_label=payload.version_label,
        raw_text=payload.resume_text,
        metadata_json={"source": "api_upload", **payload.metadata},
    )
    db.add(resume_version)
    db.commit()
    db.refresh(resume_version)
    return {
        "status": "stored",
        "user_id": user.id,
        "resume_version_id": resume_version.id,
        "version_label": resume_version.version_label,
    }


@router.post("/upload-file")
async def upload_resume_file(
    file: Annotated[UploadFile, File(...)],
    user_email: Annotated[str, Form(..., min_length=3)],
    db: Annotated[Session, Depends(get_db)],
    full_name: Annotated[str, Form(min_length=1)] = "Candidate",
    version_label: Annotated[str, Form(min_length=1, max_length=100)] = "uploaded",
) -> dict[str, Any]:
    """Upload a resume file, parse text, store the file, and create a resume version."""

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = Path(file.filename or "resume.txt").name
    suffix = Path(original_name).suffix.lower() or ".txt"
    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(await file.read())

    parsed = ResumeParser().parse(stored_path)
    if not parsed.text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Could not extract resume text.", "warnings": parsed.warnings},
        )

    user = db.query(User).filter(User.email == user_email).one_or_none()
    if user is None:
        user = User(email=user_email, full_name=full_name)
        db.add(user)
        db.flush()

    resume_version = ResumeVersion(
        user_id=user.id,
        version_label=version_label,
        raw_text=parsed.text,
        metadata_json={
            "source": "file_upload",
            "original_filename": original_name,
            "stored_path": str(stored_path),
            "parser": parsed.parser,
            "warnings": parsed.warnings,
        },
    )
    db.add(resume_version)
    db.commit()
    db.refresh(resume_version)

    return {
        "status": "parsed_and_stored",
        "user_id": user.id,
        "resume_version_id": resume_version.id,
        "version_label": resume_version.version_label,
        "parser": parsed.parser,
        "text_preview": parsed.text[:500],
        "hitl_gate": {
            "gate": "gate-1",
            "message": "Review parsed resume text and approve resume selection.",
            "approval_endpoint": "/api/v1/hitl/gate-1",
        },
    }


@router.post("/rollback")
async def rollback_resume(
    payload: RollbackRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Rollback a user's active resume to a prior version."""

    resume_version = db.get(ResumeVersion, payload.resume_version_id)
    if resume_version is None or resume_version.user_id != payload.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume version not found for user.",
        )

    metadata = dict(resume_version.metadata_json or {})
    metadata["rollback_selected"] = True
    resume_version.metadata_json = metadata
    db.add(resume_version)
    db.commit()
    return {
        "status": "rollback_selected",
        "user_id": payload.user_id,
        "resume_version_id": payload.resume_version_id,
    }
