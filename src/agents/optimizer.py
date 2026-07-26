from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings
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

    async def optimize_resume(self, resume_text: str, job_description: str) -> OptimizationResult:
        """Compatibility method returning formatted JSON and routing metadata."""

        decision = self.router.select_model(
            "Analyze and optimize this resume against the target job description.",
            {"job_description": job_description},
        )
        structured = await self.to_ats_json(resume_text, job_description)
        return OptimizationResult(
            optimized_resume=json.dumps(structured, indent=2),
            rationale=["structured ATS schema", "preserved source facts", "target context supplied"],
            model_name=decision.model_name,
            metadata={"routing": {"model_tier": decision.model_tier.value, "model_name": decision.model_name, "reason": decision.reason}, "structured_resume": structured},
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
