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
        used_fallback = bool(llm_result.metadata.get("fallback"))

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
