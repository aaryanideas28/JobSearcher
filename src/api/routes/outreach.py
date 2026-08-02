# File: src/api/routes/outreach.py
"""Outreach API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import GeneratedDocument, ResumeVersion, WorkflowSession
from src.api.dependencies import get_db
from src.workflow.tasks import send_email_outreach_task

router = APIRouter()


class OutreachDispatchRequest(BaseModel):
    """Request payload for dispatching outreach email."""

    recipient_email: str = Field(..., min_length=3)
    subject: str
    body: str
    attachments: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _resolve_resume_attachment(payload: OutreachDispatchRequest, db: Session) -> str | None:
    """Resolve a real resume file even when the frontend has no attachment list."""
    for attachment in payload.attachments:
        path = Path(str(attachment))
        if path.is_file():
            return str(path.resolve())

    session_id = payload.metadata.get("session_id")
    if session_id:
        session = db.get(WorkflowSession, str(session_id))
        session_state = session.state_json if session else {}
        if isinstance(session_state, dict):
            generated_path = session_state.get("generated_document_path")
            if generated_path and Path(str(generated_path)).is_file():
                return str(Path(str(generated_path)).resolve())

    resume_version_id = payload.metadata.get("resume_version_id")
    if not resume_version_id:
        return None

    generated = (
        db.query(GeneratedDocument)
        .filter(
            GeneratedDocument.resume_version_id == resume_version_id,
            GeneratedDocument.document_type == "optimized_resume_docx",
        )
        .order_by(GeneratedDocument.id.desc())
        .first()
    )
    if generated and Path(generated.file_path).is_file():
        return str(Path(generated.file_path).resolve())

    resume_version = db.get(ResumeVersion, resume_version_id)
    metadata = resume_version.metadata_json if resume_version else {}
    if isinstance(metadata, dict):
        for key in ("original_file_path", "stored_path"):
            path = Path(str(metadata.get(key))) if metadata.get(key) else None
            if path and path.is_file():
                return str(path.resolve())
    return None


@router.post("/dispatch")
def dispatch_outreach(
    payload: OutreachDispatchRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Queue or execute an outreach email dispatch."""
    from src.config.settings import get_settings
    settings = get_settings()
    email_payload = payload.model_dump()
    attachment = _resolve_resume_attachment(payload, db)
    email_payload["attachments"] = [attachment] if attachment else []

    if settings.celery_task_always_eager:
        result = send_email_outreach_task(email_payload)
        return {
            "status": result.get("status", "executed"),
            "recipient_email": payload.recipient_email,
            "task_id": str(uuid4()),
            "attachment": attachment,
            "result": result,
        }

    delay = getattr(send_email_outreach_task, "delay", None)
    if callable(delay):
        async_result = delay(email_payload)
        task_id = getattr(async_result, "id", str(uuid4()))
        return {
            "status": "queued",
            "recipient_email": payload.recipient_email,
            "task_id": task_id,
            "attachment": attachment,
        }

    result = send_email_outreach_task(email_payload)
    return {
        "status": result.get("status", "executed"),
        "recipient_email": payload.recipient_email,
        "task_id": str(uuid4()),
        "attachment": attachment,
        "result": result,
    }


class GenerateEmailRequest(BaseModel):
    """Request payload for drafting a personalized outreach email."""

    job_description: str = Field(..., min_length=1)
    candidate_profile: dict[str, Any] = Field(default_factory=dict)
    recipient_email: str | None = None
    company_name: str | None = None
    role_title: str | None = None


@router.post("/generate-email")
async def generate_email(payload: GenerateEmailRequest) -> dict[str, Any]:
    """Draft a personalized outreach email using OpenAI/LLM or OutreachAgent fallback."""
    from src.agents.outreach import OutreachAgent, infer_recruiter_email
    from src.config.settings import get_settings

    settings = get_settings()
    profile = payload.candidate_profile or {}
    full_name = profile.get("full_name") or profile.get("name") or "Candidate"
    target_role = profile.get("target_role") or payload.role_title or "Software Engineer"
    skills = profile.get("skills_to_highlight") or profile.get("skills") or []
    if isinstance(skills, list):
        skills_str = ", ".join(skills)
    else:
        skills_str = str(skills)

    company = payload.company_name or profile.get("company") or "Hiring Team"
    clean_company = company.lower().replace(" ", "").replace(".", "")
    recipient = payload.recipient_email or profile.get("recipient_email") or infer_recruiter_email(company)
    subject = f"Application for {target_role} - {full_name}"

    # Try OpenAI if OPENAI_API_KEY is configured
    if settings.openai_api_key:
        try:
            import json
            import httpx

            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            }
            prompt = (
                f"Write a personalized job outreach email from {full_name} applying for the {target_role} role at {company}.\n"
                f"Candidate skills: {skills_str}.\n"
                f"Job description:\n{payload.job_description}\n\n"
                "Return a JSON object with keys: 'subject', 'body'."
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You write concise, professional job application emails. Output valid JSON with keys 'subject' and 'body'.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = json.loads(data["choices"][0]["message"]["content"])
                    return {
                        "to": recipient,
                        "recipient_email": recipient,
                        "subject": content.get("subject", subject),
                        "body": content.get("body", ""),
                    }
        except Exception:
            pass

    # Fallback to OutreachAgent
    outreach_agent = OutreachAgent()
    resume_text = f"Name: {full_name}\nTarget Role: {target_role}\nSkills: {skills_str}"
    body = await outreach_agent.draft_cover_letter(
        resume_text=resume_text,
        job_description=payload.job_description,
        company_name=company,
    )

    return {
        "to": recipient,
        "recipient_email": recipient,
        "subject": subject,
        "body": body,
    }

