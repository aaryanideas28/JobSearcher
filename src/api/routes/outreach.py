# File: src/api/routes/outreach.py
"""Outreach API routes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.workflow.tasks import send_email_outreach_task

router = APIRouter()


class OutreachDispatchRequest(BaseModel):
    """Request payload for dispatching outreach email."""

    recipient_email: str = Field(..., min_length=3)
    subject: str
    body: str
    attachments: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/dispatch")
def dispatch_outreach(payload: OutreachDispatchRequest) -> dict[str, Any]:
    """Queue or execute an outreach email dispatch."""
    from src.config.settings import get_settings
    settings = get_settings()
    email_payload = payload.model_dump()

    if settings.celery_task_always_eager:
        result = send_email_outreach_task(email_payload)
        return {
            "status": result.get("status", "executed"),
            "recipient_email": payload.recipient_email,
            "task_id": str(uuid4()),
            "result": result,
        }

    delay = getattr(send_email_outreach_task, "delay", None)
    if callable(delay):
        async_result = delay(email_payload)
        task_id = getattr(async_result, "id", str(uuid4()))
        return {"status": "queued", "recipient_email": payload.recipient_email, "task_id": task_id}

    result = send_email_outreach_task(email_payload)
    return {
        "status": result.get("status", "executed"),
        "recipient_email": payload.recipient_email,
        "task_id": str(uuid4()),
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
    from src.agents.outreach import OutreachAgent
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
    recipient = payload.recipient_email or profile.get("recipient_email") or f"recruiter@{clean_company}.com"
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

