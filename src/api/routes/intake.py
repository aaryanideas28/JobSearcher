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
    full_name: str | None = None
    target_role: str = Field(..., min_length=1)
    skills_to_highlight: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_mode: str | None = None
    experience_level: str | None = None
    work_authorization: str | None = None
    template_id: str = "minimal_ats"
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
        template_id=payload.template_id,
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
        "template_id": getattr(preference, "template_id", "minimal_ats"),
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
        "template_id": getattr(preference, "template_id", "minimal_ats"),
        "metadata": preference.metadata_json,
    }


class CandidateStructuredIntake(BaseModel):
    """Candidate structured intake form data schema."""

    full_name: str = Field(..., min_length=1)
    contact_info: dict[str, Any] = Field(default_factory=dict)
    professional_summary: str = Field(default="")
    education: list[dict[str, Any]] = Field(default_factory=list)
    technical_skills: dict[str, Any] | list[Any] = Field(default_factory=dict)
    work_experience: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    achievements: list[Any] = Field(default_factory=list)


def map_structured_intake_to_json(intake: dict[str, Any]) -> dict[str, Any]:
    """Map structured intake fields to standardized resume JSON schema."""
    contact = intake.get("contact_info") or {}
    links = []
    if contact.get("linkedin"):
        links.append(contact["linkedin"])
    if contact.get("github_portfolio"):
        links.append(contact["github_portfolio"])

    # Map technical skills to list of strings
    skills = []
    tech_skills = intake.get("technical_skills") or {}
    if isinstance(tech_skills, dict):
        for k, v in tech_skills.items():
            if isinstance(v, list):
                skills.extend(v)
            elif isinstance(v, str):
                skills.extend([s.strip() for s in v.split(",") if s.strip()])
    elif isinstance(tech_skills, list):
        skills = tech_skills

    # Map education
    education = []
    for edu in intake.get("education") or []:
        degree = edu.get("degree") or ""
        spec = edu.get("specialization") or ""
        degree_str = f"{degree} in {spec}" if spec else degree
        edu_dict = {
            "institution": edu.get("institution") or "",
            "degree": degree_str,
            "end_date": str(edu.get("graduation_year") or ""),
        }
        if edu.get("cgpa_percentage"):
            edu_dict["grade"] = f"CGPA/Percentage: {edu['cgpa_percentage']}"
        education.append(edu_dict)

    # Map work experience
    experience = []
    for exp in intake.get("work_experience") or []:
        responsibilities = exp.get("responsibilities_achievements") or ""
        tech = exp.get("tech_used") or []
        tech_str = f" Technologies: {', '.join(tech)}" if tech else ""
        desc = responsibilities + tech_str
        experience.append({
            "company": exp.get("company") or "",
            "role": exp.get("role") or "",
            "start_date": "",
            "end_date": exp.get("duration") or "",
            "description": desc
        })

    # Map projects
    projects = []
    for prj in intake.get("projects") or []:
        tech = prj.get("tech_used") or []
        projects.append({
            "name": prj.get("title") or "",
            "description": prj.get("description") or "",
            "contribution_impact": prj.get("contribution_impact") or "",
            "technologies": tech,
            "link": prj.get("demo_link") or "",
        })

    # Map certifications
    certifications = []
    for cert in intake.get("certifications") or []:
        name = cert.get("name") or ""
        issuer = cert.get("issuer") or ""
        date = cert.get("date") or ""
        cert_str = f"{name} by {issuer} ({date})"
        if cert.get("credential_link"):
            cert_str += f" - Link: {cert['credential_link']}"
        certifications.append(cert_str)

    # Map achievements
    achievements = []
    for ach in intake.get("achievements") or []:
        if isinstance(ach, str):
            achievements.append(ach)
        elif isinstance(ach, dict):
            val = ach.get("name") or ach.get("description") or ach.get("details") or str(ach)
            achievements.append(val)

    return {
        "contact": {
            "name": intake.get("full_name") or "Candidate",
            "email": contact.get("email") or "candidate@example.com",
            "phone": contact.get("phone") or "",
            "location": contact.get("location") or "",
            "links": links
        },
        "summary": intake.get("professional_summary") or "",
        "skills": skills,
        "experience": experience,
        "education": education,
        "projects": projects,
        "certifications": certifications,
        "achievements": achievements
    }


def format_json_resume_to_text(resume: dict[str, Any]) -> str:
    """Format resume JSON back to a standard flat text representation."""
    lines = []
    contact = resume.get("contact") or {}
    lines.append(contact.get("name") or "Candidate")
    contact_parts = [contact.get("email"), contact.get("phone"), contact.get("location")]
    contact_parts = [c for c in contact_parts if c]
    if contact_parts:
        lines.append(" | ".join(contact_parts))
    links = contact.get("links") or []
    if links:
        lines.append(" | ".join(links))
    lines.append("\n---")

    if resume.get("summary"):
        lines.append("SUMMARY")
        lines.append(resume["summary"])
        lines.append("")

    if resume.get("skills"):
        lines.append("SKILLS")
        lines.append(", ".join(resume["skills"]))
        lines.append("")

    if resume.get("experience"):
        lines.append("EXPERIENCE")
        for exp in resume["experience"]:
            lines.append(f"{exp.get('role')} at {exp.get('company')} ({exp.get('end_date')})")
            lines.append(exp.get("description") or "")
        lines.append("")

    if resume.get("education"):
        lines.append("EDUCATION")
        for edu in resume["education"]:
            lines.append(f"{edu.get('degree')} - {edu.get('institution')} ({edu.get('end_date')})")
        lines.append("")

    if resume.get("projects"):
        lines.append("PROJECTS")
        for prj in resume["projects"]:
            lines.append(prj.get("name") or "")
            lines.append(prj.get("description") or "")
            if prj.get("contribution_impact"):
                lines.append(f"Impact: {prj['contribution_impact']}")
            technologies = prj.get("technologies") or prj.get("tech_used") or []
            if technologies:
                tech_text = ", ".join(technologies) if isinstance(technologies, list) else str(technologies)
                lines.append(f"Technologies: {tech_text}")
            if prj.get("link"):
                lines.append(f"Demo: {prj['link']}")
            lines.append("")

    if resume.get("certifications"):
        lines.append("CERTIFICATIONS")
        for cert in resume["certifications"]:
            lines.append(cert)
        lines.append("")

    if resume.get("achievements"):
        lines.append("ACHIEVEMENTS")
        for ach in resume["achievements"]:
            lines.append(ach)
        lines.append("")

    return "\n".join(lines).strip()


@router.post("/structured")
async def create_structured_candidate_profile(
    payload: CandidateStructuredIntake,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Process structured resume intake from the onboarding scratch-build flow."""
    email = payload.contact_info.get("email")
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email address is required in contact_info.",
        )

    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = User(email=email, full_name=payload.full_name)
        db.add(user)
        db.flush()
    else:
        user.full_name = payload.full_name

    mapped_json = map_structured_intake_to_json(payload.model_dump())
    raw_text = format_json_resume_to_text(mapped_json)

    from src.database.models import ResumeVersion
    resume_version = ResumeVersion(
        user_id=user.id,
        version_label="build_from_scratch",
        raw_text=raw_text,
        metadata_json={
            "intake_mode": "build_from_scratch",
            "structured_intake": payload.model_dump()
        }
    )
    db.add(resume_version)

    skills_list = mapped_json.get("skills") or []
    target_role = payload.contact_info.get("target_role") or "Software Engineer"
    preferred_locations = payload.contact_info.get("preferred_locations") or ["Remote"]
    work_mode = payload.contact_info.get("work_mode") or "Any"
    template_id = payload.contact_info.get("template_id") or "minimal_ats"

    preference = CandidatePreference(
        user_id=user.id,
        target_role=target_role,
        skills_to_highlight=skills_list,
        preferred_locations=preferred_locations,
        work_mode=work_mode,
        template_id=template_id,
        metadata_json={"intake_mode": "build_from_scratch"},
    )
    db.add(preference)
    db.commit()
    db.refresh(resume_version)
    db.refresh(preference)

    return {
        "status": "stored",
        "user_id": user.id,
        "resume_version_id": resume_version.id,
        "candidate_preference_id": preference.id,
        "target_role": target_role,
        "skills_to_highlight": skills_list,
        "preferred_locations": preferred_locations,
        "work_mode": work_mode,
        "template_id": template_id,
        "next_steps": [
            "POST /api/v1/jobs/manual",
            "POST /api/v1/workflow/manual-optimize-draft",
        ],
    }
