# File: src/api/routes/resume.py
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models import ResumeVersion, User, CandidatePreference, JobTarget
from src.api.dependencies import get_db
from src.utils.resume_parser import ResumeParser
from src.agents.job_discovery import JobDiscoveryAgent

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


async def _discover_and_persist_jobs(user_id: int, db: Session) -> list[dict[str, Any]]:
    preference = (
        db.query(CandidatePreference)
        .filter(CandidatePreference.user_id == user_id)
        .order_by(CandidatePreference.created_at.desc(), CandidatePreference.id.desc())
        .first()
    )
    query = ""
    target_role = "Software Engineer"
    skills = []
    if preference:
        target_role = preference.target_role or target_role
        skills = preference.skills_to_highlight or []
        query = f"{target_role} jobs " + " ".join(skills[:3])
    else:
        query = "Software Engineer jobs"

    agent = JobDiscoveryAgent()
    postings = await agent.discover(query=query, max_results=10)

    cards = []
    for posting in postings:
        extracted_skills = []
        desc = posting.description
        if skills:
            for skill in skills:
                if skill.lower() in desc.lower():
                    extracted_skills.append(skill)
        if not extracted_skills:
            common_skills = ["Python", "FastAPI", "Go", "Java", "SQL", "Docker", "Kubernetes", "AWS", "React", "TypeScript"]
            for s in common_skills:
                if s.lower() in desc.lower():
                    extracted_skills.append(s)

        job_target = JobTarget(
            user_id=user_id,
            company_name=posting.company,
            role_title=posting.title,
            job_url=posting.url,
            job_description=posting.description or posting.title,
            status="discovered",
            metadata_json={"extracted_skills": extracted_skills, **posting.metadata},
        )
        db.add(job_target)
        db.flush()

        cards.append({
            "job_id": job_target.id,
            "title": job_target.role_title,
            "company": job_target.company_name,
            "description": job_target.job_description,
            "extracted_skills": extracted_skills
        })
    db.commit()
    return cards


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

    discovered_jobs = await _discover_and_persist_jobs(user.id, db)

    return {
        "status": "stored",
        "user_id": user.id,
        "resume_version_id": resume_version.id,
        "version_label": resume_version.version_label,
        "job_targets": discovered_jobs,
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

    discovered_jobs = await _discover_and_persist_jobs(user.id, db)

    return {
        "status": "parsed_and_stored",
        "user_id": user.id,
        "resume_version_id": resume_version.id,
        "version_label": resume_version.version_label,
        "parser": parsed.parser,
        "text_preview": parsed.text[:500],
        "job_targets": discovered_jobs,
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


@router.get("/download/{version_id}")
async def download_resume_file(
    version_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download the compiled DOCX resume document for a version."""
    from src.database.models import GeneratedDocument
    doc = db.query(GeneratedDocument).filter(
        GeneratedDocument.resume_version_id == version_id,
        GeneratedDocument.document_type == "optimized_resume_docx",
    ).first()
    
    if not doc or not doc.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No generated document found for this resume version.",
        )
        
    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compiled document file not found on disk.",
        )
        
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )
