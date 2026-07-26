from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

<<<<<<< HEAD
from config.settings import get_settings
=======
from src.clients.ollama import OllamaClient
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
from src.agents.router import TaskComplexityRouter
from src.clients.ollama import OllamaClient
from src.workflow.state import AgentState


@dataclass(slots=True)
class OptimizationResult:
    """Structured ATS-ready resume produced by the optimizer."""

    optimized_resume: str
    rationale: list[str] = field(default_factory=list)
    model_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ResumeOptimizer:
    """Transform raw resume text into a truthful, ATS-friendly JSON document."""

    def __init__(self, router: TaskComplexityRouter | None = None, llm_client: OllamaClient | None = None) -> None:
        self.router = router or TaskComplexityRouter()
        self.llm_client = llm_client or OllamaClient()

    async def extract_resume_facts(self, resume_text: str) -> dict[str, Any]:
        """Extract stable resume facts in a machine-readable structure."""

        return await self.to_ats_json(resume_text)

    async def to_ats_json(self, resume_text: str, job_description: str = "") -> dict[str, Any]:
        """Use Ollama to return a validated JSON-first representation of a resume."""

        prompt = (
            "Convert this resume into ATS-friendly JSON only. Use exactly these keys: "
            "contact {name,email,phone,location,links}, summary, skills (array), "
            "experience (array of {title,company,location,start_date,end_date,bullets}), "
            "education (array), certifications (array), projects (array). "
            "Keep unsupported values as empty strings/arrays. Never invent facts."
            f"\n\nRESUME:\n{resume_text}\n\nTARGET JOB CONTEXT (optional):\n{job_description}"
        )
        generation = await self.llm_client.generate(
            model=get_settings().llm_model_name,
            prompt=prompt,
            system="You extract truthful resume information and respond with JSON only.",
            json_mode=True,
        )
        parsed = self._parse_json(generation.text)
        result = self._normalise_schema(parsed, resume_text)
        result["_metadata"] = {"model": generation.model, "used_fallback": generation.used_fallback, "llm": generation.metadata}
        return result

<<<<<<< HEAD
    async def optimize_resume(self, resume_text: str, job_description: str) -> OptimizationResult:
        """Compatibility method returning formatted JSON and routing metadata."""
=======
    async def optimize_resume(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: list[str] | None = None,
        target_role: str | None = None,
    ) -> OptimizationResult:
        """Produce an optimized resume draft for a target job."""
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a

        prompt = self._build_optimization_prompt(
            resume_text=resume_text,
            job_description=job_description,
            skills_to_highlight=skills_to_highlight or [],
            target_role=target_role,
        )
        decision = self.router.select_model(
<<<<<<< HEAD
            "Analyze and optimize this resume against the target job description.",
            {"job_description": job_description},
        )
        structured = await self.to_ats_json(resume_text, job_description)
        return OptimizationResult(
            optimized_resume=json.dumps(structured, indent=2),
            rationale=["structured ATS schema", "preserved source facts", "target context supplied"],
            model_name=decision.model_name,
            metadata={"routing": {"model_tier": decision.model_tier.value, "model_name": decision.model_name, "reason": decision.reason}, "structured_resume": structured},
=======
            prompt=prompt,
            context={"job_description": job_description},
        )
        generation = await self.llm_client.generate(
            model=decision.model_name,
            system=(
                "You are a precise resume optimization assistant. Preserve truthful candidate facts. "
                "Do not invent employers, dates, degrees, metrics, or certifications."
            ),
            prompt=prompt,
        )
        optimized_resume = generation.text
        if generation.used_fallback or not optimized_resume:
            optimized_resume = self._local_optimization_fallback(resume_text, job_description, skills_to_highlight or [])

        return OptimizationResult(
            optimized_resume=optimized_resume,
            rationale=[
                "routed_to_local_ollama_model",
                "preserved_source_facts",
                "aligned_resume_language_to_job_description",
            ],
            model_name=decision.model_name,
            metadata={
                "routing": {
                    "model_tier": decision.model_tier.value,
                    "model_name": decision.model_name,
                    "reason": decision.reason,
                    "estimated_complexity": decision.estimated_complexity,
                },
                "llm": generation.metadata,
                "used_fallback": generation.used_fallback,
            },
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
        )

    async def run(self, state: AgentState) -> AgentState:
        """Store structured resume JSON and serialized optimized resume in AgentState."""

        structured = await self.to_ats_json(state.resume_text, state.job_description)
        state.user_resume_json = structured
        state.extracted_facts = structured
        state.optimized_resume = json.dumps(structured, indent=2)
        state.workflow_status = "resume_optimized"
        return state

    async def generate_change_summary(self, original_text: str, optimized_text: str) -> list[str]:
        return ["Converted raw resume text into a structured ATS-friendly JSON document."] if original_text != optimized_text else ["No changes generated."]

<<<<<<< HEAD
    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        try:
            result = json.loads(text)
            return result if isinstance(result, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _normalise_schema(value: dict[str, Any], raw_text: str) -> dict[str, Any]:
        schema = {"contact": {}, "summary": "", "skills": [], "experience": [], "education": [], "certifications": [], "projects": []}
        for key in schema:
            if key in value:
                schema[key] = value[key]
        if not value:
            schema["summary"] = raw_text.strip()
        return schema
=======
        if original_text == optimized_text:
            return ["No changes generated by scaffold stub."]
        return ["Resume text was modified."]

    def _build_optimization_prompt(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: list[str],
        target_role: str | None = None,
    ) -> str:
        """Build a bounded prompt for Ollama resume optimization."""

        skills_line = ", ".join(skills_to_highlight) if skills_to_highlight else "No explicit skills provided."
        target_role_line = target_role or "Infer from job description."
        return (
            "Optimize the resume for the target job.\n\n"
            "Rules:\n"
            "- Keep only facts supported by the original resume.\n"
            "- Improve clarity, ordering, and keyword alignment.\n"
            "- Emphasize the user-selected skills only when the resume supports them.\n"
            "- Return only the rewritten resume text.\n\n"
            f"Target role: {target_role_line}\n"
            f"User-selected skills to emphasize: {skills_line}\n\n"
            f"Original resume:\n{resume_text}\n\n"
            f"Target job description:\n{job_description}\n"
        )

    def _local_optimization_fallback(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: list[str],
    ) -> str:
        """Create a deterministic optimized draft when Ollama is unavailable."""

        keywords = [word.strip(".,:;()[]").lower() for word in job_description.split()]
        unique_keywords = sorted({word for word in keywords if len(word) > 4})[:12]
        keyword_line = ", ".join(unique_keywords) if unique_keywords else "target role requirements"
        skills_line = ", ".join(skills_to_highlight) if skills_to_highlight else "not specified"
        return (
            "Optimized Resume Draft\n\n"
            f"Target Alignment Keywords: {keyword_line}\n\n"
            f"User-Selected Skills To Emphasize: {skills_line}\n\n"
            f"{resume_text.strip()}\n\n"
            "Targeted Summary\n"
            "Candidate profile aligned to the selected role while preserving the original resume facts."
        )
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
