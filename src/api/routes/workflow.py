# File: src/api/routes/workflow.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import CandidatePreference, GeneratedDocument, JobTarget, ResumeVersion, WorkflowSession
from src.agents.ats_engine import ATSEngine
from src.agents.optimizer import ResumeOptimizer
from src.agents.outreach import OutreachAgent
from src.api.dependencies import get_db
from src.clients.ollama import OllamaClient
from src.security.validation import HallucinationDetector, PromptInjectionGuard
from src.utils.pdf_compiler import PDFCompiler

router = APIRouter()
GENERATED_DIR = Path("storage_workspace/generated")


class ManualOptimizeDraftRequest(BaseModel):
    """Request to run the manual vertical workflow slice."""

    resume_version_id: int = Field(..., ge=1)
    job_target_id: int = Field(..., ge=1)
    recipient_email: str | None = Field(default=None, min_length=3)
    candidate_preference_id: int | None = Field(default=None, ge=1)
    skills_to_highlight: list[str] = Field(default_factory=list)


@router.get("/ollama/status")
async def ollama_status() -> dict[str, Any]:
    """Check whether local Ollama is reachable and which models are installed."""

    return await OllamaClient().status()


@router.post("/manual-optimize-draft")
async def manual_optimize_and_draft(
    payload: ManualOptimizeDraftRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Run resume optimization and email drafting for a manually chosen job."""

    resume_version = db.get(ResumeVersion, payload.resume_version_id)
    job_target = db.get(JobTarget, payload.job_target_id)
    if resume_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found.")
    if job_target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job target not found.")
    if resume_version.user_id != job_target.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume and job target belong to different users.")

    preference: CandidatePreference | None = None
    if payload.candidate_preference_id is not None:
        preference = db.get(CandidatePreference, payload.candidate_preference_id)
        if preference is None or preference.user_id != resume_version.user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate preference not found for user.")
    else:
        preference = (
            db.query(CandidatePreference)
            .filter(CandidatePreference.user_id == resume_version.user_id)
            .order_by(CandidatePreference.created_at.desc(), CandidatePreference.id.desc())
            .first()
        )

    selected_skills = payload.skills_to_highlight or (preference.skills_to_highlight if preference else [])
    target_role = preference.target_role if preference else job_target.role_title

    injection_guard = PromptInjectionGuard()
    resume_guard = injection_guard.inspect(resume_version.raw_text)
    job_guard = injection_guard.inspect(job_target.job_description)
    if not resume_guard.valid or not job_guard.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"resume_reasons": resume_guard.reasons, "job_reasons": job_guard.reasons},
        )

    optimizer = ResumeOptimizer()
    ats_engine = ATSEngine()
    outreach_agent = OutreachAgent()

    optimization = await optimizer.optimize_resume(
        resume_text=resume_version.raw_text,
        job_description=job_target.job_description,
        skills_to_highlight=selected_skills,
        target_role=target_role,
    )
    ats_score = await ats_engine.combined_score(optimization.optimized_resume, job_target.job_description)
    cover_letter = await outreach_agent.draft_cover_letter(
        resume_text=optimization.optimized_resume,
        job_description=job_target.job_description,
        company_name=job_target.company_name,
    )
    email_payload = outreach_agent.build_email_payload(
        recipient_email=payload.recipient_email or "review-before-send@example.com",
        subject=f"Application for {job_target.role_title} at {job_target.company_name}",
        body=cover_letter,
        attachments=[],
        metadata={
            "resume_version_id": resume_version.id,
            "job_target_id": job_target.id,
            "candidate_preference_id": preference.id if preference else None,
            "skills_to_highlight": selected_skills,
            "requires_hitl_gate": "gate-3",
        },
    )

    hallucination = HallucinationDetector().detect(
        generated_text=f"{optimization.optimized_resume}\n{cover_letter}",
        source_facts=[resume_version.raw_text, job_target.job_description],
        allowed_terms=[
            job_target.company_name,
            job_target.role_title,
            *(selected_skills or []),
            *(preference.preferred_locations if preference else []),
        ],
    )

    from src.utils.pdf_compiler import HTML
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    
    if HTML is not None:
        pdf_html = _resume_text_to_html(optimization.optimized_resume, job_target.role_title)
        pdf_path = GENERATED_DIR / f"resume_v{resume_version.id}_job{job_target.id}.pdf"
        PDFCompiler().compile_to_file(pdf_html, pdf_path)
        attached_path = pdf_path
        document_type = "optimized_resume_pdf"
    else:
        txt_path = GENERATED_DIR / f"resume_v{resume_version.id}_job{job_target.id}.txt"
        txt_path.write_text(optimization.optimized_resume, encoding="utf-8")
        attached_path = txt_path
        document_type = "optimized_resume_txt"

    email_payload.attachments.append(str(attached_path))

    resume_version.optimized_text = optimization.optimized_resume
    resume_version.ats_score = ats_score.score
    metadata = dict(resume_version.metadata_json or {})
    metadata["latest_workflow"] = {
        "job_target_id": job_target.id,
        "candidate_preference_id": preference.id if preference else None,
        "skills_to_highlight": selected_skills,
        "routing": optimization.metadata.get("routing"),
        "ats_method": ats_score.method,
        "hallucination_valid": hallucination.valid,
    }
    resume_version.metadata_json = metadata
    db.add(resume_version)
    
    generated_document = GeneratedDocument(
        user_id=resume_version.user_id,
        resume_version_id=resume_version.id,
        document_type=document_type,
        file_path=str(attached_path),
        metadata_json={"job_target_id": job_target.id, "source": "manual_workflow"},
    )
    db.add(generated_document)
    
    session_id = str(uuid4())
    workflow_session = WorkflowSession(
        id=session_id,
        user_id=resume_version.user_id,
        resume_version_id=resume_version.id,
        job_target_id=job_target.id,
        status="draft_ready_for_human_review",
        state_json={
            "optimized_resume": optimization.optimized_resume,
            "email_draft": asdict(email_payload),
            "ats_score": ats_score.score,
            "candidate_preference_id": preference.id if preference else None,
            "skills_to_highlight": selected_skills,
            "generated_document_path": str(attached_path),
        },
    )
    db.add(workflow_session)
    db.commit()

    return {
        "status": "draft_ready_for_human_review",
        "session_id": session_id,
        "resume_version_id": resume_version.id,
        "job_target_id": job_target.id,
        "routing": optimization.metadata.get("routing"),
        "skills_to_highlight": selected_skills,
        "candidate_preference_id": preference.id if preference else None,
        "ats_score": ats_score.score,
        "ats_details": ats_score.details,
        "optimized_resume": optimization.optimized_resume,
        "generated_pdf": str(attached_path),
        "change_summary": optimization.change_summary,
        "email_draft": asdict(email_payload),
        "quality_checks": {
            "hallucination_valid": hallucination.valid,
            "hallucination_reasons": hallucination.reasons,
        },
        "hitl_gate": {
            "gate": "gate-3",
            "message": "Review optimized resume and email draft before dispatch.",
            "approval_endpoint": "/api/v1/hitl/gate-3",
            "approval_payload": {
                "session_id": session_id,
                "approved": True,
                "reviewer_email": None,
                "notes": "Approved optimized resume and email draft.",
            },
        },
    }


def _resume_text_to_html(resume_text: str, title: str) -> str:
    """Convert plain optimized resume text to simple printable HTML."""

    escaped = (
        resume_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title} Resume</title>"
        "<style>body{font-family:Arial,sans-serif;margin:42px;line-height:1.45;color:#111827}"
        "h1{font-size:22px;margin-bottom:18px} .resume{font-size:12px}</style>"
        "</head><body>"
        f"<h1>{title} - Optimized Resume</h1><div class='resume'>{escaped}</div>"
        "</body></html>"
    )
