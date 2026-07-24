# File: src/agents/ats_engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    TfidfVectorizer = None  # type: ignore[assignment]
    cosine_similarity = None  # type: ignore[assignment]


@dataclass(slots=True)
class ATSScore:
    """Normalized ATS score and explanatory metadata."""

    score: float
    method: str
    details: dict[str, Any]


class ATSEngine:
    """Score resume-to-job fit with lexical and LLM-assisted strategies."""

    def score_with_tfidf(self, resume_text: str, job_description: str) -> ATSScore:
        """Compute a TF-IDF cosine similarity score between resume and job text."""

        if not resume_text.strip() or not job_description.strip():
            return ATSScore(score=0.0, method="tfidf", details={"reason": "empty_input"})

        if TfidfVectorizer is None or cosine_similarity is None:
            return ATSScore(
                score=self._score_with_token_overlap(resume_text, job_description),
                method="token_overlap_fallback",
                details={"reason": "sklearn_unavailable"},
            )

        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([resume_text, job_description])
        score = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
        return ATSScore(score=round(score, 4), method="tfidf", details={"features": len(vectorizer.get_feature_names_out())})

    async def score_with_llm(self, resume_text: str, job_description: str) -> ATSScore:
        """Placeholder for model-based ATS scoring."""

        _ = (resume_text, job_description)
        return ATSScore(score=0.0, method="llm_stub", details={"reason": "not_implemented"})

    async def combined_score(self, resume_text: str, job_description: str) -> ATSScore:
        """Combine lexical and LLM scores into one normalized ATS score."""

        tfidf_score = self.score_with_tfidf(resume_text, job_description)
        llm_score = await self.score_with_llm(resume_text, job_description)
        combined = round((tfidf_score.score * 0.7) + (llm_score.score * 0.3), 4)
        return ATSScore(
            score=combined,
            method="weighted_tfidf_llm",
            details={"tfidf": tfidf_score.details, "llm": llm_score.details},
        )

    def _score_with_token_overlap(self, resume_text: str, job_description: str) -> float:
        """Fallback similarity scorer used when scikit-learn is unavailable."""

        resume_tokens = set(resume_text.lower().split())
        job_tokens = set(job_description.lower().split())
        if not resume_tokens or not job_tokens:
            return 0.0
        return round(len(resume_tokens & job_tokens) / len(job_tokens), 4)
