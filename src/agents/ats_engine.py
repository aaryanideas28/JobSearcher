# File: src/agents/ats_engine.py
"""Embedding-based semantic matching and regex ATS engine."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Set

from src.clients.embeddings import get_embedding
from src.workflow.state import AgentState

STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "hed", "hell", "hes", "her", "here",
    "heres", "hers", "herself", "him", "himself", "his", "how", "hows", "i",
    "id", "ill", "im", "ive", "if", "in", "into", "is", "isn't", "it", "its",
    "itself", "lets", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "shed", "shell", "shes", "should", "shouldn't", "so", "some", "such", "than",
    "that", "thats", "the", "their", "theirs", "them", "themselves", "then",
    "there", "theres", "these", "they", "theyd", "theyll", "theyre", "theyve",
    "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "wasn't", "we", "wed", "well", "were", "weren't", "weve", "what",
    "whats", "whatever", "when", "whens", "where", "wheres", "which", "while",
    "who", "whos", "whom", "why", "whys", "with", "won't", "would", "wouldn't",
    "you", "youd", "youll", "youre", "youve", "your", "yours", "yourself", "yourselves"
}


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))


@dataclass(slots=True)
class ATSScore:
    """Normalized ATS score and explanatory metadata."""

    score: float
    method: str
    details: Dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        if key == "overall_score":
            return self.score
        return self.details.get(key)


class ATSEngine:
    """Analyze resume and job description using regex keyword matching and embedding cosine similarity."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    def calculate_ats_score(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Compute hybrid ATS score and return strict JSON-compatible dictionary."""
        if not resume_text.strip() or not job_description.strip():
            return {
                "overall_score": 0.0,
                "missing_keywords": [],
                "semantic_gaps": [],
            }

        # 1. Regex Keyword Extraction & Matching
        jd_keywords = self._extract_keywords(job_description)
        resume_keywords = self._extract_keywords(resume_text)

        if jd_keywords:
            matched_keywords = jd_keywords & resume_keywords
            missing_keywords = sorted(list(jd_keywords - resume_keywords))
            keyword_score = len(matched_keywords) / len(jd_keywords)
        else:
            missing_keywords = []
            keyword_score = 1.0

        # 2. Semantic Bullet-Point Matching via Embeddings
        jd_bullets = self._extract_bullets(job_description)
        resume_bullets = self._extract_bullets(resume_text)

        if not resume_bullets:
            resume_bullets = [resume_text]

        resume_embeddings = [get_embedding(bullet) for bullet in resume_bullets]
        full_resume_emb = get_embedding(resume_text)

        semantic_scores: List[float] = []
        semantic_gaps: List[Dict[str, Any]] = []

        for req in jd_bullets:
            req_emb = get_embedding(req)
            sims = [cosine_similarity(req_emb, r_emb) for r_emb in resume_embeddings]
            sims.append(cosine_similarity(req_emb, full_resume_emb))
            max_sim = max(sims) if sims else 0.0
            semantic_scores.append(max_sim)

            if max_sim < 0.70:
                semantic_gaps.append({
                    "requirement": req,
                    "similarity": round(max_sim, 4),
                })

        semantic_gaps.sort(key=lambda g: g["similarity"])
        semantic_score = (sum(semantic_scores) / len(semantic_scores)) if semantic_scores else 1.0

        # 3. Hybrid Combined Score
        overall_score = round(0.4 * keyword_score + 0.6 * semantic_score, 4)

        return {
            "overall_score": max(0.0, min(1.0, overall_score)),
            "missing_keywords": missing_keywords,
            "semantic_gaps": semantic_gaps,
        }

    async def combined_score(self, resume_text: str, job_description: str) -> ATSScore:
        """Async entry point returning ATSScore dataclass containing the JSON payload details."""
        details = self.calculate_ats_score(resume_text, job_description)
        return ATSScore(
            score=details["overall_score"],
            method="hybrid_embedding_regex",
            details=details,
        )

    async def run(self, state: AgentState) -> AgentState:
        """Write ATS analysis and score into shared workflow state."""
        resume = state.get("optimized_resume") or state.get("resume_text") or ""
        job_desc = state.get("job_description") or ""
        score = await self.combined_score(resume, job_desc)
        state["ats_score"] = score.score
        state["matching_score"] = score.score
        state.setdefault("metadata", {})["ats_analysis"] = score.details
        state["workflow_status"] = "ats_analyzed"
        return state

    def _extract_keywords(self, text: str) -> Set[str]:
        """Regex tokenization (lowercase, normalize) to extract meaningful keywords."""
        raw_tokens = re.findall(r"\b[a-zA-Z0-9+#.-]+\b", text.lower())
        keywords = set()
        for token in raw_tokens:
            cleaned = token.strip(".-")
            if len(cleaned) >= 2 and cleaned not in STOP_WORDS:
                keywords.add(cleaned)
        return keywords

    def _extract_bullets(self, text: str) -> List[str]:
        """Split text into distinct bullet points or requirement statements."""
        lines = text.splitlines()
        bullets = []
        for line in lines:
            cleaned = re.sub(r"^[\s•\-\*\d\.\)]+", "", line).strip()
            if len(cleaned) > 10:
                bullets.append(cleaned)
        return bullets if bullets else [text.strip()]
