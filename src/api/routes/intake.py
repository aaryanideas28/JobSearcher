# File: src/api/routes/intake.py
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models import CandidatePreference, User
from src.api.dependencies import get_db

router = APIRouter()


class IntakeQuestion(BaseModel):
    """Question definition a frontend or CLI can render for the user."""

    key: str
    prompt: str
    input_type: str
    required: bool = True
    examples: list[str] = Field(default_factory=list)


class CandidatePreferenceRequest(BaseModel):
    """Candidate intake profile used to personalize resume optimization."""

    email: str = Field(..., min_length=3)
    full_name: str = Field(default="Candidate", min_length=1)
    target_role: str = Field(..., min_length=1)
    skills_to_highlight: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_mode: str | None = "Any"
    experience_level: str | None = None
    work_authorization: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/questions", response_model=list[IntakeQuestion])
async def get_intake_questions() -> list[IntakeQuestion]:
    """Return the questions required before optimization can be personalized."""

    return [
        IntakeQuestion(
            key="resume_file_or_text",
            prompt="Upload your resume or paste your resume text.",
            input_type="file_or_text",
            examples=["resume.pdf", "resume.docx", "plain resume text"],
        ),
        IntakeQuestion(
            key="target_role",
            prompt="What role are you targeting?",
            input_type="text",
            examples=["Backend Engineer", "Data Scientist", "ML Platform Engineer"],
        ),
        IntakeQuestion(
            key="skills_to_highlight",
            prompt="Which skills should the resume emphasize?",
            input_type="list",
            examples=["Python", "FastAPI", "Docker", "SQLAlchemy"],
        ),
        IntakeQuestion(
            key="preferred_locations",
            prompt="Where do you prefer to work?",
            input_type="list",
            required=False,
            examples=["Remote", "Bengaluru", "Hyderabad"],
        ),
        IntakeQuestion(
            key="experience_level",
            prompt="What experience level should the search target?",
            input_type="text",
            required=False,
            examples=["entry", "mid", "senior"],
        ),
    ]


@router.post("/profile")
async def create_or_update_candidate_profile(
    payload: CandidatePreferenceRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Store candidate skills, target role, and search preferences."""

    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is None:
        user = User(email=payload.email, full_name=payload.full_name)
        db.add(user)
        db.flush()
    else:
        user.full_name = payload.full_name

    preference = CandidatePreference(
        user_id=user.id,
        target_role=payload.target_role,
        experience_level=payload.experience_level,
        skills_to_highlight=payload.skills_to_highlight,
        preferred_locations=payload.preferred_locations,
        work_mode=payload.work_mode,
        work_authorization=payload.work_authorization,
        metadata_json=payload.metadata,
    )
    db.add(preference)
    db.commit()
    db.refresh(preference)

    return {
        "status": "stored",
        "user_id": user.id,
        "candidate_preference_id": preference.id,
        "target_role": preference.target_role,
        "skills_to_highlight": preference.skills_to_highlight,
        "preferred_locations": preference.preferred_locations,
        "work_mode": getattr(preference, "work_mode", "Any"),
        "next_steps": [
            "POST /api/v1/resume/upload-file or /api/v1/resume/upload",
            "POST /api/v1/jobs/manual",
            "POST /api/v1/workflow/manual-optimize-draft",
        ],
    }


@router.get("/profile/{user_id}/latest")
async def get_latest_candidate_profile(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Return the latest candidate preference profile for a user."""

    preference = (
        db.query(CandidatePreference)
        .filter(CandidatePreference.user_id == user_id)
        .order_by(CandidatePreference.created_at.desc(), CandidatePreference.id.desc())
        .first()
    )
    if preference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate preference not found.")

    return {
        "user_id": preference.user_id,
        "candidate_preference_id": preference.id,
        "target_role": preference.target_role,
        "experience_level": preference.experience_level,
        "skills_to_highlight": preference.skills_to_highlight,
        "preferred_locations": preference.preferred_locations,
        "work_mode": getattr(preference, "work_mode", "Any"),
        "work_authorization": preference.work_authorization,
        "metadata": preference.metadata_json,
    }
