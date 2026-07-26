from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from config.settings import get_settings
from src.clients.ollama import OllamaClient
from src.workflow.state import AgentState

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover
    TfidfVectorizer = None  # type: ignore[assignment]
    cosine_similarity = None  # type: ignore[assignment]


@dataclass(slots=True)
class ATSScore:
    """Normalized ATS score and explanatory metadata."""

    score: float
    method: str
    details: dict[str, Any]


class ATSEngine:
    """Analyze resume/job fit with deterministic similarity and local Ollama analysis."""

    def __init__(self, llm_client: OllamaClient | None = None) -> None:
        self.llm_client = llm_client or OllamaClient()

    def score_with_tfidf(self, resume_text: str, job_description: str) -> ATSScore:
        if not resume_text.strip() or not job_description.strip():
            return ATSScore(0.0, "tfidf", {"reason": "empty_input"})
        if TfidfVectorizer is None or cosine_similarity is None:
            return ATSScore(self._score_with_token_overlap(resume_text, job_description), "token_overlap_fallback", {"reason": "sklearn_unavailable"})
        matrix = TfidfVectorizer(stop_words="english").fit_transform([resume_text, job_description])
        return ATSScore(round(float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0]), 4), "tfidf", {})

    async def score_with_llm(self, resume_text: str, job_description: str) -> ATSScore:
        """Ask llama3 for keyword gaps and ATS-safe formatting issues as JSON."""

        if not resume_text.strip() or not job_description.strip():
            return ATSScore(0.0, "llm", {"reason": "empty_input"})
        prompt = (
            "Compare the resume to the job description for ATS fit. Return JSON only with: "
            "score (number 0..1), matched_keywords (array), missing_keywords (array), "
            "formatting_issues (array), recommendations (array). Do not invent candidate experience.\n\n"
            f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_description}"
        )
        generation = await self.llm_client.generate(
            model=get_settings().llm_model_name,
            prompt=prompt,
            system="You are an ATS analyst. Provide concise evidence-based JSON.",
            json_mode=True,
        )
        payload = self._parse_json(generation.text)
        score = self._normalise_score(payload.get("score")) if payload else 0.0
        details = payload or {"reason": "invalid_or_unavailable_llm_response"}
        details["llm"] = generation.metadata
        details["used_fallback"] = generation.used_fallback
        return ATSScore(score, "llm_keyword_gap_analysis", details)

    async def combined_score(self, resume_text: str, job_description: str) -> ATSScore:
        tfidf_score = self.score_with_tfidf(resume_text, job_description)
        llm_score = await self.score_with_llm(resume_text, job_description)
        return ATSScore(
            round((tfidf_score.score * 0.7) + (llm_score.score * 0.3), 4),
            "weighted_tfidf_llm",
            {"tfidf": tfidf_score.details, "llm": llm_score.details, "tfidf_score": tfidf_score.score, "llm_score": llm_score.score},
        )

    async def run(self, state: AgentState) -> AgentState:
        """Write ATS analysis and score into the shared workflow state."""

        resume = state.optimized_resume or state.resume_text
        score = await self.combined_score(resume, state.job_description)
        state.ats_score = score.score
        state.matching_score = score.score
        state.metadata["ats_analysis"] = score.details
        state.workflow_status = "ats_analyzed"
        return state

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _normalise_score(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(score / 100 if score > 1 else score, 1.0))

    @staticmethod
    def _score_with_token_overlap(resume_text: str, job_description: str) -> float:
        resume_tokens, job_tokens = set(resume_text.lower().split()), set(job_description.lower().split())
        return round(len(resume_tokens & job_tokens) / len(job_tokens), 4) if job_tokens else 0.0
