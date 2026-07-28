# File: src/agents/optimizer.py
"""Resume optimization agent with Ollama routing and deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.agents.router import RoutingDecision, TaskComplexityRouter
from src.clients.ollama import OllamaClient


@dataclass(slots=True)
class OptimizationResult:
    """Output produced by the resume optimizer."""

    optimized_resume: str
    change_summary: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class ResumeOptimizer:
    """Agent responsible for tailoring a resume to a selected job target."""

    def __init__(
        self,
        router: TaskComplexityRouter | None = None,
        llm_client: OllamaClient | None = None,
    ) -> None:
        self.router = router or TaskComplexityRouter()
        self.llm_client = llm_client or OllamaClient()

    def extract_resume_facts(self, resume_text: str) -> dict[str, Any]:
        """Extract simple facts from resume text for downstream validation."""
        words = [word.strip(".,:;()[]{}") for word in resume_text.split()]
        skills = sorted({word for word in words if word and word[:1].isupper()})[:25]
        return {"skills": skills, "raw_length": len(resume_text), "source": "resume_text"}

    async def build_resume_from_skills(self, skills: list[str], target_role: str) -> dict[str, Any]:
        """Synthesize a complete, professional JSON resume schema from a list of skills and target role."""
        import json
        from src.security.validation import JSONSchemaValidator
        
        skills_str = ", ".join(skills)
        prompt = (
            f"You are an expert resume writer. Synthesize a complete, professional, ATS-compliant JSON resume for a candidate targeting the role: '{target_role}' with the following skills: {skills_str}.\n"
            "The JSON must strictly conform to the following schema structure, with no extra fields:\n"
            "{\n"
            "  \"contact\": {\n"
            "    \"name\": \"Candidate Name\",\n"
            "    \"email\": \"candidate@example.com\",\n"
            "    \"phone\": \"+1-123-456-7890\",\n"
            "    \"location\": \"City, State\",\n"
            "    \"links\": []\n"
            "  },\n"
            "  \"summary\": \"Summary text emphasizing targeted skills\",\n"
            "  \"skills\": [\"skill1\", \"skill2\"],\n"
            "  \"experience\": [\n"
            "    {\n"
            "      \"company\": \"Company Name\",\n"
            "      \"role\": \"Role Title\",\n"
            "      \"start_date\": \"2020-01\",\n"
            "      \"end_date\": \"Present\",\n"
            "      \"description\": \"Key accomplishment bullet points using target skills\"\n"
            "    }\n"
            "  ],\n"
            "  \"education\": [\n"
            "    {\n"
            "      \"institution\": \"University\",\n"
            "      \"degree\": \"Bachelor of Science\",\n"
            "      \"start_date\": \"2016-09\",\n"
            "      \"end_date\": \"2020-05\"\n"
            "    }\n"
            "  ],\n"
            "  \"certifications\": [],\n"
            "  \"projects\": [\n"
            "    {\n"
            "      \"name\": \"Project name\",\n"
            "      \"description\": \"Project details\"\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Return only valid JSON matching this schema."
        )

        routing = self.router.route(prompt)
        try:
            llm_result = await self.llm_client.generate(
                model=routing.model_name,
                prompt=prompt,
                json_mode=True
            )
            text = llm_result.text.strip()
            if text:
                parsed_data = json.loads(text)
                schema_model, validation = JSONSchemaValidator().parse_resume(parsed_data)
                if validation.valid and schema_model is not None:
                    return schema_model.model_dump()
        except Exception:
            pass

        # Fallback synthesis schema
        fallback_resume = {
            "contact": {
                "name": "Candidate",
                "email": "candidate@example.com",
                "phone": "+1-123-456-7890",
                "location": "Remote",
                "links": []
            },
            "summary": f"Professional and results-driven specialist targeting the {target_role} role, with strong expertise in {', '.join(skills[:5])}.",
            "skills": skills,
            "experience": [
                {
                    "company": "Tech Solutions Inc.",
                    "role": f"Senior {target_role}",
                    "start_date": "2021-01",
                    "end_date": "Present",
                    "description": f"Led development and deployment of systems focusing on {', '.join(skills[:3])}. Optimized application performance and designed scalable architectures."
                },
                {
                    "company": "Innovation Labs",
                    "role": target_role,
                    "start_date": "2018-06",
                    "end_date": "2020-12",
                    "description": f"Developed key features and maintained platforms using {', '.join(skills[2:5] if len(skills) >= 5 else skills)}. Collaborated with cross-functional teams to deliver projects on time."
                }
            ],
            "education": [
                {
                    "institution": "University of Technology",
                    "degree": "Bachelor of Science in Computer Science",
                    "start_date": "2014-09",
                    "end_date": "2018-05"
                }
            ],
            "certifications": [],
            "projects": [
                {
                    "name": f"Automated {target_role} System",
                    "description": f"Designed and built a core system utilizing {', '.join(skills[:2])} to automate critical business workflows, improving efficiency by 30%."
                }
            ]
        }
        return fallback_resume

    async def optimize_resume(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: list[str] | None = None,
        target_role: str | None = None,
    ) -> OptimizationResult:
        """Generate an optimized resume draft using Ollama when available."""
        prompt = self._build_optimization_prompt(
            resume_text=resume_text,
            job_description=job_description,
            skills_to_highlight=skills_to_highlight or [],
            target_role=target_role,
        )
        routing = self.router.route(prompt)
        llm_result = await self.llm_client.generate(model=routing.model_name, prompt=prompt)
        optimized_resume = llm_result.text.strip()
        used_fallback = llm_result.used_fallback or (optimized_resume == "{}")

        if not optimized_resume or used_fallback:
            optimized_resume = self._local_optimization_fallback(
                resume_text=resume_text,
                job_description=job_description,
                skills_to_highlight=skills_to_highlight or [],
            )

        return OptimizationResult(
            optimized_resume=optimized_resume,
            change_summary=["Resume text was modified."],
            metadata={
                "routing": self._routing_to_dict(routing),
                "llm": llm_result.metadata,
                "used_fallback": used_fallback,
            },
        )

    def _build_optimization_prompt(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: list[str],
        target_role: str | None,
    ) -> str:
        """Build a concise instruction prompt for local LLM resume optimization."""
        skills = ", ".join(skills_to_highlight) if skills_to_highlight else "No explicit skills selected"
        role = target_role or "the target role"
        return (
            "You are an expert resume editor. Tailor the resume to the job while preserving truthful facts.\n"
            f"Target role: {role}\n"
            f"Skills to emphasize: {skills}\n\n"
            "Original resume:\n"
            f"{resume_text}\n\n"
            "Job description:\n"
            f"{job_description}\n\n"
            "Return only the optimized resume text with clear sections."
        )

    def _local_optimization_fallback(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: list[str],
    ) -> str:
        """Create a deterministic draft when the local LLM is unavailable."""
        keywords = self._extract_keywords(job_description)
        skills_line = ", ".join(skills_to_highlight) if skills_to_highlight else "No user-selected skills provided"
        return (
            "Optimized Resume Draft\n\n"
            f"Target Alignment Keywords: {', '.join(keywords)}\n\n"
            f"User-Selected Skills To Emphasize: {skills_line}\n\n"
            f"{resume_text.strip()}\n\n"
            "Targeted Summary\n"
            "Candidate profile aligned to the selected role while preserving the original resume facts."
        )

    def _extract_keywords(self, text: str, limit: int = 12) -> list[str]:
        """Extract simple keyword candidates from the job description."""
        stop_words = {"and", "the", "for", "with", "you", "our", "are", "will", "this", "that", "from"}
        words = [word.lower().strip(".,:;()[]{}") for word in text.split()]
        unique = sorted({word for word in words if len(word) > 3 and word not in stop_words})
        return unique[:limit]

    def _routing_to_dict(self, decision: RoutingDecision) -> dict[str, Any]:
        """Serialize a routing decision."""
        return {
            "model_tier": decision.model_tier.value,
            "model_name": decision.model_name,
            "reason": decision.reason,
            "estimated_complexity": decision.estimated_complexity,
        }
