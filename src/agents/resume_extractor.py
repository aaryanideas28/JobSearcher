"""Fast structured extraction of verified candidate details from resume text."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, field_validator

from src.agents.router import TaskComplexityRouter
from src.clients.ollama import OllamaClient


class ResumeDetails(BaseModel):
    """Small structured profile used to prefill candidate intake."""

    candidate_name: str = ""
    email: str = ""
    phone: str = ""
    core_skills: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("core_skills")
    @classmethod
    def normalize_skills(cls, skills: list[str]) -> list[str]:
        unique: list[str] = []
        for skill in skills:
            normalized = str(skill).strip()
            if normalized and normalized.lower() not in {item.lower() for item in unique}:
                unique.append(normalized)
        return unique[:10]


def _fallback_extract(raw_text: str) -> ResumeDetails:
    """Return useful deterministic fields when structured generation is unavailable."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidate_name = ""
    for line in lines[:8]:
        if line.lower().startswith("name:"):
            candidate_name = line.split(":", 1)[1].strip()
            break
    if not candidate_name and lines and len(lines[0]) <= 80 and "@" not in lines[0]:
        candidate_name = lines[0]

    email_match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", raw_text)
    phone_match = re.search(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)", raw_text)
    known_skills = [
        "Python", "FastAPI", "Django", "Java", "JavaScript", "TypeScript", "React",
        "SQL", "PostgreSQL", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Go",
        "C++", "Git", "Redis", "Celery", "Machine Learning",
    ]
    skills = [skill for skill in known_skills if re.search(rf"\b{re.escape(skill)}\b", raw_text, re.IGNORECASE)]
    return ResumeDetails(
        candidate_name=candidate_name,
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0).strip() if phone_match else "",
        core_skills=skills,
    )


async def extract_resume_details(
    raw_text: str,
    *,
    llm_client: OllamaClient | None = None,
    router: TaskComplexityRouter | None = None,
) -> ResumeDetails:
    """Extract candidate identity and up to ten core skills from resume text."""
    if not raw_text or not raw_text.strip():
        return ResumeDetails()

    client = llm_client or OllamaClient()
    model_router = router or TaskComplexityRouter()
    prompt = (
        "Extract candidate details from the resume below. Return only valid JSON with exactly these fields: "
        "candidate_name (string), email (string), phone (string), core_skills (array of no more than 10 strings). "
        "Use empty strings or an empty array when a value is not present. Do not invent information.\n\n"
        f"Resume:\n{raw_text}"
    )

    try:
        decision = model_router.route(prompt)
        generation = await client.generate(
            model=decision.model_name,
            prompt=prompt,
            json_mode=True,
        )
        parsed = json.loads(generation.text or "{}")
        return ResumeDetails.model_validate(parsed)
    except Exception:
        return _fallback_extract(raw_text)
