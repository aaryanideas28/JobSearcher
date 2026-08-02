# File: src/agents/outreach.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.agents.router import TaskComplexityRouter
from src.clients.ollama import OllamaClient

@dataclass(slots=True)
class EmailPayload:
    """Outbound email payload ready for queue dispatch."""

    recipient_email: str
    subject: str
    body: str
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def sanitize_company_name(company: str) -> str:
    import re
    company = str(company).strip()
    loc_patterns = [
        r'\b(bangalore|bengaluru|mumbai|delhi|noida|gurgaon|hyderabad|pune|chennai|karnataka|maharashtra)\b',
        r'\b(london|ny|nyc|sf|san francisco|california|texas|uk|us|usa|india|germany|singapore)\b',
        r'\b(remote|hybrid|on-site|onsite)\b'
    ]
    for pattern in loc_patterns:
        company = re.sub(pattern, '', company, flags=re.IGNORECASE)
    company = re.sub(r'^[,\s\-:|–|•|]+|[,\s\-:|–|•|]+$', '', company)
    company = re.sub(r'\s+', ' ', company).strip()
    if not company or company.lower() in {"unknown company", "unknown", "hiring company", "company"}:
        company = "Hiring Team"
    return company


def infer_recruiter_email(company_name: str) -> str:
    """Build the deterministic recruiter address used when a job has no contact email."""
    import re

    company_slug = re.sub(r"[^a-z0-9]", "", str(company_name).lower())
    return f"recruiter@{company_slug}.com" if company_slug else "review-before-send@example.com"


def extract_contact_email(text: str) -> str:
    """Extract an email address explicitly published in job data, if present."""
    import re

    match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text or "")
    return match.group(0) if match else ""


class OutreachAgent:
    """Agent for cover letter generation and email payload assembly."""

    def __init__(self, router: TaskComplexityRouter | None = None, llm_client: OllamaClient | None = None) -> None:
        self.router = router or TaskComplexityRouter(complexity_threshold=0.35)
        self.llm_client = llm_client or OllamaClient()

    async def draft_cover_letter(
        self,
        resume_text: str,
        job_description: str,
        company_name: str,
        candidate_name: str | None = None,
        target_role: str | None = None,
        candidate_skills: list[str] | None = None,
    ) -> str:
        """Draft a cover letter for a target company and job."""
        candidate_name = candidate_name or ""
        target_role = target_role or ""
        for line in resume_text.split("\n"):
            if not candidate_name and line.lower().startswith("name:"):
                candidate_name = line.split(":", 1)[1].strip()
            elif not target_role and line.lower().startswith("target role:"):
                target_role = line.split(":", 1)[1].strip()

        return await self.generate_outreach_email(
            resume_text=resume_text,
            job_description=job_description,
            company_name=company_name,
            candidate_name=candidate_name or "the candidate",
            target_role=target_role or "the advertised role",
            candidate_skills=candidate_skills or [],
        )

    async def generate_outreach_email(
        self,
        resume_text: str,
        job_description: str,
        company_name: str,
        candidate_name: str = "Candidate",
        target_role: str = "Software Engineer",
        candidate_skills: list[str] | None = None,
    ) -> str:
        """Generate a metrics-driven, high-converting outreach email applying the 3-paragraph pitch structure."""
        clean_company = sanitize_company_name(company_name)
        skills_text = ", ".join(candidate_skills or []) or "Extract relevant skills from the raw resume"
        
        # Structure the LLM prompt precisely following the three-paragraph layout
        prompt = (
            "Write a personalized, high-converting job outreach email body applying for a target role.\n\n"
            "The email body MUST have exactly three paragraphs structured as follows:\n\n"
            "Paragraph 1 (Direct Hook): State candidate's name, target role, and immediate value proposition tailored to the company's core tech stack.\n\n"
            "Paragraph 2 (Key Achievements): 2-3 concrete bullet points highlighting key technical achievements from the resume (e.g. latency cuts, high RPS handling, system scale, performance stats).\n\n"
            "Paragraph 3 (Call to Action): Concise closing requesting a brief conversation and referencing the attached DOCX resume.\n\n"
            f"You are drafting an outreach email for {candidate_name}.\n"
            f"Target Role: {target_role}\n"
            f"Target Company: Extract directly from the job description below; do not guess.\n"
            f"Candidate Skills to Highlight: {skills_text}\n\n"
            f"Reference the following raw resume for tone and additional metrics:\n{resume_text}\n\n"
            f"Selected Job Description:\n{job_description}\n\n"
            "Resume handling instructions: The resume may be structured JSON or plain text extracted from a PDF. "
            "If it is plain text, extract the candidate's key skills, roles, projects, and responsibilities directly from that text. "
            "If structured metrics are unavailable, describe the candidate's skills and responsibilities without inventing numbers, employers, dates, or achievements. "
            "Use the provided target role exactly. Extract the target company name directly from the job description. "
            "Never write placeholders such as 'Target Company', '[Company Name]', 'Candidate', or 'Software Engineer' when the supplied context contains a more specific value. "
            "Output only the three paragraphs, formatted cleanly. Do not include a subject line or header metadata in the body."
        )
        
        decision = self.router.select_model(prompt, {"job_description": job_description})
        generation = await self.llm_client.generate(
            model=decision.model_name,
            system="You write high-converting, metric-driven job application outreach emails.",
            prompt=prompt,
        )
        
        if generation.used_fallback or not generation.text:
            explicit_skills = [skill.strip() for skill in (candidate_skills or []) if skill.strip()]
            known_skills = [
                "Python", "FastAPI", "Django", "Java", "JavaScript", "TypeScript", "React",
                "SQL", "PostgreSQL", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Go",
                "C++", "Git", "Redis", "Celery", "Machine Learning",
            ]
            extracted_skills = [
                skill for skill in known_skills
                if skill.lower() in resume_text.lower() or skill.lower() in job_description.lower()
            ]
            skills_found = list(dict.fromkeys(explicit_skills + extracted_skills))[:6]
            skills_text = ", ".join(skills_found) or "the technical skills shown in the attached resume"
            role_text = target_role or "the advertised role"
            company_text = clean_company or "the hiring team"
            return (
                f"Dear {company_text} Hiring Team,\n\n"
                f"My name is {candidate_name}, and I am writing to express my interest in the {role_text} position. "
                f"My background includes {skills_text}, with experience relevant to the requirements described in your job posting.\n\n"
                f"I would welcome the opportunity to contribute these skills to {company_text}. "
                f"The attached resume provides additional details about my projects, responsibilities, and achievements related to {role_text}.\n\n"
                f"I would appreciate a brief conversation about how my experience can support the {role_text} team. "
                "Please find my resume attached in DOCX format.\n\n"
                "Best regards,\n"
                f"{candidate_name}"
            )

            # Try to extract key skills for fallback list
            skills_found = []
            for s in ["Python", "FastAPI", "Go", "Java", "SQL", "Docker", "Kubernetes", "AWS", "React", "TypeScript", "GCP"]:
                if s.lower() in resume_text.lower():
                    skills_found.append(s)
            skills_bullet = ", ".join(skills_found[:4]) if skills_found else "backend engineering and scale"
            primary_skill = skills_found[0] if skills_found else "modern tech"
            
            return (
                f"Dear {clean_company} Hiring Team,\n\n"
                f"My name is {candidate_name}, and I am writing to express my interest in the {target_role} position. "
                f"I bring immediate value in developing high-scale systems, backend architectures, and core tech like {skills_bullet}.\n\n"
                "Here are a few highlights of my technical achievements:\n"
                "• Optimized service response latency by 35% using caching and database connection pooling.\n"
                f"• Scaled systems using {primary_skill} and cloud infrastructure to handle 5,000+ requests per second with high availability.\n"
                "• Wrote robust automated test suites, improving code coverage metrics to 90%+.\n\n"
                "I would appreciate a brief conversation to discuss how my experience fits your goals. "
                "Please find my resume attached in DOCX format.\n\n"
                "Best regards,\n"
                f"{candidate_name}"
            )
        return generation.text

    def build_email_payload(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EmailPayload:
        """Build a normalized email payload for delivery workers."""

        return EmailPayload(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            attachments=attachments or [],
            metadata=metadata or {},
        )
