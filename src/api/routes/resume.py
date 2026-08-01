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
    template_id: str = "minimal_ats"
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _discover_and_persist_jobs(user_id: int, db: Session, source: str = "tavily") -> list[dict[str, Any]]:
    preference = (
        db.query(CandidatePreference)
        .filter(CandidatePreference.user_id == user_id)
        .order_by(CandidatePreference.created_at.desc(), CandidatePreference.id.desc())
        .first()
    )
    query = ""
    target_role = "Software Engineer"
    skills = []
    preferred_locations = []
    work_mode = "Any"
    if preference:
        target_role = preference.target_role or target_role
        skills = preference.skills_to_highlight or []
        preferred_locations = preference.preferred_locations or []
        work_mode = getattr(preference, "work_mode", "Any")
        query = f"{target_role} jobs " + " ".join(skills[:3])
    else:
        query = "Software Engineer jobs"

    agent = JobDiscoveryAgent()
    postings = await agent.discover(
        query=query,
        max_results=6,
        source=source,
        preferred_locations=preferred_locations,
        work_mode=work_mode,
    )

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
            preferred_locations=preferred_locations,
            work_mode=work_mode,
            metadata_json={"extracted_skills": extracted_skills, **posting.metadata},
        )
        db.add(job_target)
        db.flush()

        cards.append({
            "job_id": job_target.id,
            "title": job_target.role_title,
            "company": job_target.company_name,
            "description": job_target.job_description,
            "extracted_skills": extracted_skills,
            "job_url": job_target.job_url
        })
    db.commit()
    return cards


@router.post("/upload")
async def upload_resume(
    payload: ResumeUploadRequest,
    db: Annotated[Session, Depends(get_db)],
    source: str = "tavily",
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
        template_id=payload.template_id,
        metadata_json={"source": "api_upload", **payload.metadata},
    )
    db.add(resume_version)
    db.commit()
    db.refresh(resume_version)

    discovered_jobs = await _discover_and_persist_jobs(user.id, db, source=source)

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
    template_id: Annotated[str, Form(min_length=1)] = "minimal_ats",
    source: str = "tavily",
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

    # Maintain original uploaded file reference
    original_file_name = f"user_{user.id}_original{suffix}"
    original_file_path = UPLOAD_DIR / original_file_name
    original_file_path.write_bytes(stored_path.read_bytes())

    resume_version = ResumeVersion(
        user_id=user.id,
        version_label=version_label,
        raw_text=parsed.text,
        template_id=template_id,
        metadata_json={
            "source": "file_upload",
            "original_filename": original_name,
            "stored_path": str(stored_path),
            "original_file_path": str(original_file_path),
            "parser": parsed.parser,
            "warnings": parsed.warnings,
        },
    )
    db.add(resume_version)
    db.commit()
    db.refresh(resume_version)

    discovered_jobs = await _discover_and_persist_jobs(user.id, db, source=source)


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


def get_download_file_response(user_id: int | None, version_id: int, db: Session) -> FileResponse:
    from src.database.models import GeneratedDocument, WorkflowSession
    
    # 1. Fetch resume version to check metadata
    resume_version = db.get(ResumeVersion, version_id)
    if not resume_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume version not found.",
        )
        
    resolved_user_id = user_id or resume_version.user_id
    
    # 2. Check if optimization was approved
    approve_optimization = True
    
    # Check session state
    session = (
        db.query(WorkflowSession)
        .filter(
            WorkflowSession.user_id == resolved_user_id,
            WorkflowSession.resume_version_id == version_id
        )
        .order_by(WorkflowSession.created_at.desc())
        .first()
    )
    if session and session.state_json:
        if session.state_json.get("approve_optimization") == False:
            approve_optimization = False
            
    # Check metadata
    if resume_version.metadata_json and resume_version.metadata_json.get("approve_optimization") == False:
        approve_optimization = False
        
    if not approve_optimization:
        # Point directly to the original file path
        import glob
        files = glob.glob(f"storage_workspace/uploads/user_{resolved_user_id}_original.*")
        if not files and resume_version.metadata_json:
            stored_path = resume_version.metadata_json.get("stored_path")
            if stored_path:
                files = [stored_path]
                
        if files:
            original_path = Path(files[0])
            if original_path.exists():
                suffix = original_path.suffix.lower()
                media_type = "application/octet-stream"
                if suffix == ".pdf":
                    media_type = "application/pdf"
                elif suffix == ".docx":
                    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif suffix in (".txt", ".md"):
                    media_type = "text/plain"
                    
                return FileResponse(
                    path=original_path,
                    media_type=media_type,
                    filename=original_path.name
                )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original uploaded file not found.",
        )
        
    # Else serve the compiled DOCX
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


@router.get("/download/{version_id}")
async def download_resume_file(
    version_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download the compiled DOCX resume document for a version."""
    return get_download_file_response(None, version_id, db)


@router.get("/download/{user_id}/{version_id}")
async def download_resume_file_by_user_and_version(
    user_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download the original uploaded resume file by user and version."""
    return get_download_file_response(user_id, version_id, db)


class CalculateATSRequest(BaseModel):
    """Request payload for ATS match score calculation."""

    tailored_resume: str = Field(..., min_length=1)
    job_description: str = Field(..., min_length=1)


@router.post("/calculate-ats")
async def calculate_ats(payload: CalculateATSRequest) -> dict[str, Any]:
    """Compare tailored resume and job description, returning an ATS match score (0-100)."""
    from src.agents.ats_engine import ATSEngine

    engine = ATSEngine()
    result = engine.calculate_ats_score(payload.tailored_resume, payload.job_description)
    raw_score = result.get("overall_score", 0.0)
    int_score = int(round(raw_score * 100)) if raw_score <= 1.0 else int(round(raw_score))
    int_score = max(0, min(100, int_score))

    return {
        "ats_score": int_score,
        "score": int_score,
        "missing_keywords": result.get("missing_keywords", []),
        "semantic_gaps": result.get("semantic_gaps", []),
    }

