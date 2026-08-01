# File: src/api/routes/workflow.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models import CandidatePreference, GeneratedDocument, JobTarget, ResumeVersion, WorkflowSession
from src.agents.ats_engine import ATSEngine
from src.agents.optimizer import ResumeOptimizer, OptimizationResult
from src.agents.outreach import OutreachAgent
from src.api.dependencies import get_db
from src.clients.ollama import OllamaClient
from src.security.validation import HallucinationDetector, PromptInjectionGuard
from src.utils.docx_compiler import DocxCompiler

router = APIRouter()
GENERATED_DIR = Path("storage_workspace/generated")


class ManualOptimizeDraftRequest(BaseModel):
    """Request to run the manual vertical workflow slice."""

    resume_version_id: int = Field(..., ge=1)
    job_target_id: int = Field(..., ge=1)
    recipient_email: str | None = Field(default=None, min_length=3)
    candidate_preference_id: int | None = Field(default=None, ge=1)
    skills_to_highlight: list[str] = Field(default_factory=list)
    intake_mode: str = Field(default="upload")
    structured_intake: dict[str, Any] = Field(default_factory=dict)
    client_session_id: str | None = None


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

    from src.api.progress import progress_hub

    session_id = payload.client_session_id or str(uuid4())
    if payload.client_session_id:
        await progress_hub.publish(session_id, {
            "type": "progress",
            "state": "optimizing",
            "pct": 75,
            "message": "Optimizing resume bullet points & ATS keywords...",
        })
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

    if not resume_version.raw_text or not resume_version.raw_text.strip():
        if payload.intake_mode == "upload" and not payload.structured_intake:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select an intake option: Upload an existing resume OR fill out the 'Build from Scratch' form.",
            )
        # Synthesize a structured JSON resume from skills if building from scratch with skills
        resume_dict = await optimizer.build_resume_from_skills(selected_skills, target_role)
        import json
        optimization = OptimizationResult(
            optimized_resume=json.dumps(resume_dict, indent=2),
            change_summary=["Synthesized structured resume from user skills and target role."],
            metadata={"routing": {"model_tier": "large", "model_name": "huggingface", "reason": "No baseline resume upload"}},
        )
    else:
        # Proceed with resume optimization pipeline to boost ATS score to >85%
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

    storage_dir = Path("storage_workspace/final_documents") / f"user_{resume_version.user_id}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    docx_path = Path("final_documents") / f"user_{resume_version.user_id}" / f"resume_v{resume_version.id}.docx"

    optimized_resume_json = None
    try:
        import json
        optimized_resume_json = json.loads(optimization.optimized_resume)
    except Exception:
        from src.utils.docx_compiler import DocxCompiler
        parsed_resume = DocxCompiler().parse_resume_text_to_dict(optimization.optimized_resume)
        if not parsed_resume.get("contact", {}).get("name") or parsed_resume["contact"]["name"] == "Candidate":
            parsed_resume["contact"]["name"] = resume_version.user.full_name
        if not parsed_resume.get("contact", {}).get("email"):
            parsed_resume["contact"]["email"] = resume_version.user.email
        optimized_resume_json = parsed_resume

    docx_compiler = DocxCompiler()
    docx_path = docx_compiler.compile_docx_state({
        "optimized_resume_json": optimized_resume_json,
        "user_resume_json": optimized_resume_json,
        "target_role": target_role,
        "target_company": job_target.company_name,
        "user_id": resume_version.user_id,
        "attempt_count": resume_version.id,
        "template_id": getattr(resume_version, "template_id", "minimal_ats")
    }, docx_path)

    attached_path = docx_path.resolve()
    document_type = "optimized_resume_docx"

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
    
    ats_score_val = ats_score.score
    if ats_score_val <= 1.0:
        ats_score_percent = ats_score_val * 100.0
    else:
        ats_score_percent = ats_score_val

    is_low_ats = False if payload.intake_mode == "build_from_scratch" else (ats_score_percent < 80)
    status_str = "PAUSED_FOR_HUMAN_OPTIMIZATION_APPROVAL" if is_low_ats else "draft_ready_for_human_review"

    workflow_session = WorkflowSession(
        id=session_id,
        user_id=resume_version.user_id,
        resume_version_id=resume_version.id,
        job_target_id=job_target.id,
        status=status_str,
        state_json={
            "optimized_resume": optimization.optimized_resume,
            "email_draft": asdict(email_payload),
            "ats_score": ats_score.score,
            "candidate_preference_id": preference.id if preference else None,
            "skills_to_highlight": selected_skills,
            "generated_document_path": str(attached_path),
            "optimization_recommended": is_low_ats,
            "intake_mode": payload.intake_mode,
            "structured_intake": payload.structured_intake,
        },
    )
    db.add(workflow_session)
    db.commit()

    if payload.client_session_id:
        await progress_hub.publish(session_id, {
            "type": "progress",
            "state": "complete",
            "pct": 100,
            "message": "Optimization complete!",
        })

    return {
        "status": status_str,
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
