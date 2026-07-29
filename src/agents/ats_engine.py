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


COMMON_TECHNICAL_SKILLS: Set[str] = {
    # Programming Languages
    "python", "javascript", "typescript", "golang", "go", "java", "c++", "c#", "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "html", "css", "bash", "shell", "perl", "dart", "objective-c", "elixir", "haskell",
    # Frameworks & Libraries
    "fastapi", "flask", "django", "spring", "spring boot", "react", "react native", "next.js", "nextjs", "vue", "vuejs", "angular", "express", "node.js", "nodejs", "rails", "laravel", "pytorch", "tensorflow", "keras", "scikit-learn", "numpy", "pandas", "sklearn", "jquery", "bootstrap", "tailwind", "hibernate", "prisma", "sequelize", "graphql", "grpc", "spring boot", "play framework", "net core", "asp.net", "symfony", "codeigniter",
    # Databases & Caching
    "postgresql", "postgres", "mysql", "mongodb", "sqlite", "redis", "elasticsearch", "cassandra", "mariadb", "dynamodb", "oracle", "neo4j", "firebase", "couchdb", "influxdb", "clickhouse", "memcached",
    # DevOps, Cloud & Systems
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "jenkins", "terraform", "ansible", "git", "github", "gitlab", "prometheus", "grafana", "nginx", "apache", "linux", "unix", "heroku", "netlify", "vercel", "ci/cd", "cicd", "circleci", "github actions", "datadog", "new relic", "vagrant", "openstack", "helm",
    # Architecture, Concepts & Tools
    "rest", "restful", "api", "apis", "microservices", "agile", "scrum", "kanban", "oop", "mvc", "tdd", "devops", "cloud computing", "machine learning", "deep learning", "artificial intelligence", "ai", "ml", "nlp", "llm", "llms", "rag", "langchain", "llama", "huggingface", "gitflow", "distributed systems", "system design", "data structures", "algorithms", "web3", "blockchain", "oauth", "jwt", "saml", "active directory",
    # Testing & Testing Tooling
    "testing", "unit test", "integration test", "pytest", "unittest", "mocha", "jest", "selenium", "playwright", "cypress", "junit", "testng", "cucumber", "postman"
}


class ATSEngine:
    """Analyze resume and job description using case-insensitive Weighted Skill Overlap algorithm."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    def _extract_technical_skills(self, text: str) -> Set[str]:
        """Scan text and match exact terms from COMMON_TECHNICAL_SKILLS (case-insensitive)."""
        normalized = text.lower()
        matched = set()
        
        for skill in COMMON_TECHNICAL_SKILLS:
            escaped = re.escape(skill)
            # Use custom boundaries for skills with special chars (+, #, .) to avoid boundary mismatch
            if skill.endswith("++") or skill.endswith("#") or skill.startswith("."):
                pattern = r"(?:^|(?<=\s|/|,|;))" + escaped + r"(?:$|(?=\s|/|,|;|\.))"
            else:
                pattern = r"\b" + escaped + r"\b"
                
            if re.search(pattern, normalized):
                matched.add(skill)
        return matched

    def calculate_ats_score(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Compute hybrid calibrated ATS score (0-100) using Weighted Skill Overlap and Density."""
        if not resume_text.strip() or not job_description.strip():
            return {
                "ats_score": 0,
                "overall_score": 0.0,
                "matched_skills": [],
                "missing_skills": [],
                "missing_keywords": [],
                "semantic_gaps": [],
            }

        # 1. Skill Extraction
        jd_skills = self._extract_technical_skills(job_description)
        resume_skills = self._extract_technical_skills(resume_text)

        matched_skills = jd_skills & resume_skills
        missing_skills = jd_skills - resume_skills

        # 2. Skill Coverage Score (70% component)
        if jd_skills:
            coverage_score = len(matched_skills) / len(jd_skills)
        else:
            coverage_score = 1.0

        # 3. Role & Experience Keyword Density Score (30% component)
        # Extract general tokens from JD (excluding skills and stop words)
        jd_tokens = self._extract_keywords(job_description)
        jd_role_tokens = jd_tokens - {s.lower() for s in jd_skills}

        if jd_role_tokens:
            resume_tokens = self._extract_keywords(resume_text)
            matched_role_tokens = jd_role_tokens & resume_tokens
            density_score = len(matched_role_tokens) / len(jd_role_tokens)
        else:
            density_score = 1.0

        # 4. Calibrate to realistic 75% - 95% range for matching resumes
        if not jd_skills:
            ats_score = int(85.0 + (density_score * 10.0))
        elif len(matched_skills) == 0:
            ats_score = int(density_score * 30.0)
        else:
            # Linear mapping to realistic ranges
            ats_score = int(70.0 + (coverage_score * 20.0) + (density_score * 5.0))

        ats_score = max(0, min(100, ats_score))

        # Build list of semantic gap objects for compatibility
        semantic_gaps = []
        for s in sorted(list(missing_skills)):
            semantic_gaps.append({
                "requirement": f"Missing Technical Skill: {s.title()}",
                "similarity": 0.0,
            })

        return {
            "ats_score": ats_score,
            "overall_score": float(ats_score) / 100.0,
            "matched_skills": sorted(list(matched_skills)),
            "missing_skills": sorted(list(missing_skills)),
            "missing_keywords": sorted(list(missing_skills)),
            "semantic_gaps": semantic_gaps,
        }

    def calculate_score(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Wrapper method alias to satisfy calculate_score calls directly."""
        return self.calculate_ats_score(resume_text, job_description)

    async def combined_score(self, resume_text: str, job_description: str) -> ATSScore:
        """Async entry point returning ATSScore dataclass containing the JSON payload details."""
        details = self.calculate_ats_score(resume_text, job_description)
        return ATSScore(
            score=details["overall_score"],
            method="weighted_skill_overlap",
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
