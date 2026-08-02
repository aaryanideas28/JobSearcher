# File: src/agents/ats_engine.py
"""Embedding-based semantic matching and regex ATS engine."""

from __future__ import annotations

import asyncio
import copy
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Set

from src.clients.embeddings import get_embedding
from src.config.constants import (
    FORMATTING_ARTIFACT_PATTERNS,
    METRIC_PATTERNS_REGEX,
    PENALTY_WEIGHTS,
    WEAK_ACTION_VERBS,
    WEAK_VERBS_REGEX,
)
from src.workflow.state import AgentState


# =============================================================================
# STOP WORDS / GENERIC JOB DESCRIPTION WORDS
# =============================================================================

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
    "you", "youd", "youll", "youre", "youve", "your", "yours", "yourself",
    "yourselves",
}

JOB_FILLER_WORDS: Set[str] = {
    "seeking", "looking", "responsibilities", "requirements", "experience",
    "years", "candidate", "ability", "working", "strong", "team", "role",
    "work", "skills", "knowledge", "environment", "equal", "opportunity",
    "employment", "job", "description", "full", "time", "part", "location",
    "preferred", "qualifications", "duty", "duties", "ideal", "successful",
}


# =============================================================================
# TECHNICAL SKILLS
# =============================================================================

COMMON_TECHNICAL_SKILLS: Set[str] = {
    # Programming Languages
    "python", "javascript", "typescript", "golang", "go", "java",
    "c++", "c#", "rust", "ruby", "php", "swift", "kotlin", "scala",
    "r", "sql", "html", "css", "bash", "shell", "perl", "dart",
    "objective-c", "elixir", "haskell",

    # Frameworks & Libraries
    "fastapi", "flask", "django", "spring", "spring boot",
    "react", "react native", "next.js", "nextjs", "vue", "vuejs",
    "angular", "express", "node.js", "nodejs", "rails", "laravel",
    "pytorch", "tensorflow", "keras", "scikit-learn", "numpy",
    "pandas", "sklearn", "jquery", "bootstrap", "tailwind",
    "hibernate", "prisma", "sequelize", "graphql", "grpc",
    "play framework", "net core", "asp.net", "symfony", "codeigniter",

    # AI / LLM
    "langchain", "huggingface", "hugging face", "transformers",
    "rag", "retrieval augmented generation",
    "retrieval-augmented generation",
    "prompt engineering", "llm", "llms", "openai",
    "computer vision", "nlp", "natural language processing",

    # Vector Databases
    "chromadb", "chroma", "faiss", "pinecone", "weaviate", "milvus",

    # Databases & Caching
    "postgresql", "postgres", "mysql", "mongodb", "sqlite",
    "redis", "elasticsearch", "cassandra", "mariadb", "dynamodb",
    "oracle", "neo4j", "firebase", "couchdb", "influxdb",
    "clickhouse", "memcached",

    # DevOps, Cloud & Systems
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure",
    "jenkins", "terraform", "ansible", "git", "github", "gitlab",
    "prometheus", "grafana", "nginx", "apache", "linux", "unix",
    "heroku", "netlify", "vercel", "ci/cd", "cicd", "circleci",
    "github actions", "datadog", "new relic", "vagrant",
    "openstack", "helm",

    # Architecture / Concepts
    "rest", "restful", "api", "apis", "microservices",
    "agile", "scrum", "kanban", "oop", "mvc", "tdd",
    "devops", "cloud computing", "machine learning",
    "deep learning", "artificial intelligence", "ai", "ml",
    "gitflow", "distributed systems", "system design",
    "data structures", "algorithms", "web3", "blockchain",
    "oauth", "jwt", "saml", "active directory",

    # Testing
    "testing", "unit test", "integration test", "pytest",
    "unittest", "mocha", "jest", "selenium", "playwright",
    "cypress", "junit", "testng", "cucumber", "postman",
}


SKILL_ALIASES: Dict[str, str] = {
    "k8s": "kubernetes",
    "nodejs": "node.js",
    "nextjs": "next.js",
    "vuejs": "vue",
    "sklearn": "scikit-learn",
    "cicd": "ci/cd",
    "apis": "api",
    "llms": "llm",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "hugging face": "huggingface",
    "chroma": "chromadb",
    "retrieval augmented generation": "rag",
    "retrieval-augmented generation": "rag",
}


# =============================================================================
# JOB REQUIREMENT MARKERS
# =============================================================================

REQUIRED_MARKERS = re.compile(
    r"\b(?:required|must(?: have)?|mandatory|minimum|need(?:ed)?|qualifications)\b",
    re.IGNORECASE,
)

PREFERRED_MARKERS = re.compile(
    r"\b(?:preferred|nice to have|bonus|plus|desired|ideal)\b",
    re.IGNORECASE,
)


# =============================================================================
# STANDARD RESUME HEADINGS
# =============================================================================

STANDARD_RESUME_HEADINGS: Dict[str, tuple[str, ...]] = {
    "summary": (
        "summary",
        "profile",
        "profile summary",
        "professional summary",
        "career objective",
        "objective",
    ),
    "experience": (
        "experience",
        "professional experience",
        "work experience",
        "employment",
        "work history",
    ),
    "education": (
        "education",
        "academic background",
        "academic qualifications",
    ),
    "skills": (
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
    ),
}


# =============================================================================
# ACTION VERBS
# =============================================================================

STRONG_VERB_REPLACEMENTS: Dict[str, str] = {
    "assisted": "Supported",
    "assisted with": "Supported",
    "helped": "Contributed to",
    "helped to": "Contributed to",
    "worked on": "Developed",
    "worked with": "Collaborated with",
    "responsible for": "Managed",
    "duties included": "Delivered",
    "handled": "Managed",
    "tasked with": "Executed",
    "participated in": "Contributed to",
    "served as": "Led",
    "contributed to": "Advanced",
    "involved in": "Executed",
    "managed to": "Achieved",
    "attempted to": "Implemented",
    "supported": "Enabled",
    "aided": "Supported",
    "was part of": "Collaborated on",
    "took part in": "Contributed to",
    "dealt with": "Resolved",
}


ACTION_VERB_REGEX = re.compile(
    r"""
    ^(?:
        achieved|accelerated|architected|automated|built|
        collaborated|configured|containerized|created|
        decreased|delivered|deployed|designed|developed|
        drove|enabled|engineered|enhanced|established|
        evaluated|executed|fine-tuned|generated|implemented|
        improved|increased|integrated|introduced|launched|
        led|maintained|managed|migrated|optimized|
        orchestrated|processed|reduced|refactored|
        resolved|scaled|spearheaded|streamlined|
        tested|trained|transformed
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# =============================================================================
# METRIC DETECTION
# =============================================================================

# This supplements METRIC_PATTERNS_REGEX from constants.py.
#
# Examples detected:
#   25%
#   99.9%
#   2x
#   3×
#   $25,000
#   ₹2 lakh is not handled perfectly, but ₹200000 is
#   10K users
#   5 APIs
#   20,000 records
#   120 ms
#   top 10
#   ranked 4
#
ATS_METRIC_REGEX = re.compile(
    r"""
    (?:
        # Percentages
        (?<!\w)\d+(?:\.\d+)?\s*%

        # Multipliers: 2x, 3.5x, 4×
        |(?<!\w)\d+(?:\.\d+)?\s*[x×](?!\w)

        # Currency
        |(?:\$|₹|€|£)\s*\d[\d,.]*(?:\s*(?:k|m|b|thousand|million|billion))?

        # Compact scale: 10K+, 2M, etc.
        |(?<!\w)\d+(?:\.\d+)?\s*(?:k|m|b)\+?(?!\w)

        # Explicit measurable counts
        |\b\d[\d,]*(?:\.\d+)?\+?\s+
        (?:
            users?|customers?|clients?|records?|documents?|files?|
            requests?|queries?|transactions?|models?|apis?|endpoints?|
            services?|microservices?|projects?|features?|tests?|
            datasets?|images?|samples?|teams?|engineers?|developers?|
            hours?|minutes?|seconds?|days?|weeks?|months?|
            repositories?|commits?|bugs?|issues?|pipelines?|servers?|
            containers?|applications?|deployments?
        )\b

        # Time / latency units
        |\b\d+(?:\.\d+)?\s*
        (?:
            ms|milliseconds?|sec|secs|seconds?|
            min|mins|minutes?|hr|hrs|hours?
        )\b

        # Ranking
        |\b(?:top|ranked?|rank)\s*#?\s*\d+\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# =============================================================================
# HELPER
# =============================================================================

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


# =============================================================================
# SCORE MODEL
# =============================================================================

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


# =============================================================================
# ATS ENGINE
# =============================================================================

class ATSEngine:
    """
    Analyze resume and job description using weighted skill overlap,
    keyword relevance, and ATS-quality penalties.

    Important:
    Metric density is calculated only from achievement/responsibility
    bullets, not from every line in the resume.
    """

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    # =========================================================================
    # SKILL MATCHING
    # =========================================================================

    @staticmethod
    def _skill_pattern(skill: str) -> re.Pattern[str]:
        """
        Create a safer regex for technical skills.

        Word boundaries do not work reliably for skills such as C++ and C#,
        so lookarounds are used instead.
        """

        escaped = re.escape(skill)

        return re.compile(
            rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )

    def _extract_technical_skills(self, text: str) -> Set[str]:
        """Extract normalized technical skills from text."""

        matched: Set[str] = set()

        for skill in COMMON_TECHNICAL_SKILLS:
            if self._skill_pattern(skill).search(text):
                matched.add(SKILL_ALIASES.get(skill, skill))

        return matched

    def _classify_job_skills(
        self,
        job_description: str,
        job_skills: Set[str],
    ) -> tuple[Set[str], Set[str]]:
        """
        Classify job skills as required or preferred.

        Skills not explicitly marked preferred fall back to required.
        """

        required: Set[str] = set()
        preferred: Set[str] = set()

        for line in job_description.splitlines():
            line_skills = self._extract_technical_skills(line)

            if not line_skills:
                continue

            preferred_match = PREFERRED_MARKERS.search(line)

            if preferred_match:
                before_preferred = line[:preferred_match.start()]
                after_preferred = line[preferred_match.end():]

                if REQUIRED_MARKERS.search(before_preferred):
                    required.update(
                        self._extract_technical_skills(before_preferred)
                    )

                preferred_after = self._extract_technical_skills(
                    after_preferred
                )

                if preferred_after:
                    preferred.update(preferred_after)

                elif not REQUIRED_MARKERS.search(before_preferred):
                    preferred.update(line_skills)

            elif REQUIRED_MARKERS.search(line):
                required.update(line_skills)

        preferred &= job_skills

        # Legacy-safe fallback:
        # any detected JD skill not explicitly preferred is required.
        required = (
            required | (job_skills - preferred)
        ) & job_skills

        return required, preferred

    def _skill_evidence(
        self,
        resume_text: str,
        skills: Set[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Return evidence showing where matched skills appear.
        """

        lines = [
            line.strip()
            for line in resume_text.splitlines()
            if line.strip()
        ]

        evidence: Dict[str, Dict[str, Any]] = {}

        for skill in sorted(skills):
            pattern = self._skill_pattern(skill)

            matches = [
                line
                for line in lines
                if pattern.search(line)
            ]

            experience_matches = [
                line
                for line in matches
                if any(
                    marker in line.lower()
                    for marker in (
                        "experience",
                        "project",
                        "engineer",
                        "developer",
                        "intern",
                        "analyst",
                        "manager",
                    )
                )
            ]

            evidence[skill] = {
                "locations": (
                    "experience_or_project"
                    if experience_matches
                    else "resume_text"
                ),
                "snippets": (experience_matches or matches)[:3],
            }

        return evidence

    # =========================================================================
    # STRUCTURE ANALYSIS
    # =========================================================================

    def _analyze_structure(
        self,
        resume_text: str,
    ) -> Dict[str, Any]:
        """
        Analyze resume structure without making missing sections hard failures.
        """

        normalized = resume_text.lower()

        headings = {
            section: any(
                re.search(
                    rf"(?im)^\s*{re.escape(alias)}\s*:?\s*$",
                    normalized,
                )
                for alias in aliases
            )
            for section, aliases in STANDARD_RESUME_HEADINGS.items()
        }

        has_email = bool(
            re.search(
                r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b",
                resume_text,
                re.IGNORECASE,
            )
        )

        has_phone = bool(
            re.search(
                r"(?:\+?\d[\d\s().-]{7,}\d)",
                resume_text,
            )
        )

        warnings: List[str] = []

        if not has_email:
            warnings.append("missing email")

        if not has_phone:
            warnings.append("missing phone")

        return {
            "detected_headings": [
                name
                for name, found in headings.items()
                if found
            ],
            "missing_headings": [
                name
                for name, found in headings.items()
                if not found
            ],
            "contact": {
                "email_detected": has_email,
                "phone_detected": has_phone,
            },
            "parse_warnings": warnings,
        }

    @staticmethod
    def _clean_structure_warnings(
        structure: Dict[str, Any],
    ) -> None:
        """Remove empty warnings."""

        structure["parse_warnings"] = [
            warning
            for warning in structure.get("parse_warnings", [])
            if warning
        ]

    # =========================================================================
    # BULLET EXTRACTION
    # =========================================================================

    def _extract_bullets(self, text: str) -> List[str]:
        """
        Extract explicit resume bullets.

        This intentionally avoids treating every long line as a bullet.
        """

        bullets: List[str] = []

        bullet_pattern = re.compile(
            r"^\s*(?:[•●▪◦\-*]|\d+[.)])\s+(.+)$"
        )

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            match = bullet_pattern.match(line)

            if not match:
                continue

            cleaned = match.group(1).strip()

            if cleaned:
                bullets.append(cleaned)

        return bullets

    def _extract_achievement_bullets(
        self,
        text: str,
    ) -> List[str]:
        """
        Extract accomplishment/responsibility statements.

        This function prevents:
        - contact details
        - education lines
        - skill lists
        - headings
        - technology lists
        - URLs

        from being included in metric-density calculations.
        """

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        bullets: List[str] = []

        explicit_pattern = re.compile(
            r"^\s*(?:[•●▪◦\-*]|\d+[.)])\s+"
        )

        heading_pattern = re.compile(
            r"""
            ^(?:
                professional\s+summary|
                profile\s+summary|
                career\s+objective|
                summary|
                profile|
                objective|
                professional\s+experience|
                work\s+experience|
                experience|
                employment|
                work\s+history|
                education|
                academic\s+background|
                academic\s+qualifications|
                technical\s+skills|
                core\s+competencies|
                competencies|
                skills|
                projects?|
                certifications?|
                achievements?|
                contact|
                languages?
            )\s*:?\s*$
            """,
            re.IGNORECASE | re.VERBOSE,
        )

        skill_category_pattern = re.compile(
            r"""
            ^(?:
                programming\s+languages?|
                languages?|
                frameworks?|
                libraries?|
                databases?|
                developer\s+tools?|
                development\s+tools?|
                tools?|
                technologies?|
                cloud|
                cloud\s+platforms?|
                concepts?|
                ai/ml|
                machine\s+learning|
                vector\s+databases?|
                backend|
                frontend
            )\s*:
            """,
            re.IGNORECASE | re.VERBOSE,
        )

        for line in lines:
            explicit_bullet = bool(
                explicit_pattern.match(line)
            )

            cleaned = explicit_pattern.sub(
                "",
                line,
                count=1,
            ).strip()

            if not cleaned:
                continue

            # Ignore section headings.
            if heading_pattern.fullmatch(cleaned):
                continue

            # Ignore contact information.
            if re.search(
                r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b",
                cleaned,
                re.IGNORECASE,
            ):
                continue

            # Ignore common URL/profile lines.
            if re.search(
                r"(?:https?://|www\.|linkedin\.com|github\.com)",
                cleaned,
                re.IGNORECASE,
            ):
                continue

            # Ignore categorized skill lines.
            if skill_category_pattern.search(cleaned):
                continue

            word_count = len(cleaned.split())

            if word_count < 6:
                continue

            # Explicit bullet = candidate achievement statement.
            if explicit_bullet:
                bullets.append(cleaned)
                continue

            # UI textarea may provide plain lines with no bullet marker.
            # Require an action-oriented opening in that case.
            if ACTION_VERB_REGEX.search(cleaned):
                bullets.append(cleaned)

        return bullets

    # =========================================================================
    # METRIC ANALYSIS
    # =========================================================================

    def _contains_metric(self, text: str) -> bool:
        """
        Detect whether a statement contains measurable evidence.

        Uses both the project's configured regex and a broader fallback.
        """

        if not text:
            return False

        try:
            configured_match = bool(
                METRIC_PATTERNS_REGEX.search(text)
            )
        except Exception:
            configured_match = False

        return configured_match or bool(
            ATS_METRIC_REGEX.search(text)
        )

    def _analyze_metric_density(
        self,
        text: str,
    ) -> tuple[int, List[str]]:
        """
        Analyze quantified impact across achievement bullets only.

        IMPORTANT:
        Skills, contact details, education, company names, headings,
        technology lists, etc. are not included in the denominator.
        """

        bullets = self._extract_achievement_bullets(text)

        if not bullets:
            return 0, []

        metric_bullets = [
            bullet
            for bullet in bullets
            if self._contains_metric(bullet)
        ]

        total_count = len(bullets)
        metric_count = len(metric_bullets)

        ratio = metric_count / total_count

        issues: List[str] = []
        penalty = 0

        # With only 1-2 achievement bullets, a ratio-based penalty is
        # statistically noisy and can create misleading recommendations.
        if total_count >= 3 and ratio < 0.50:
            percentage = int(round(ratio * 100))

            issues.append(
                f"{metric_count}/{total_count} achievement bullets "
                f"contain measurable results "
                f"({percentage}%; target: 50%+)"
            )

            penalty = PENALTY_WEIGHTS.get(
                "low_metric_ratio_penalty",
                15,
            )

        return penalty, issues

    # =========================================================================
    # IMPACT VERBS
    # =========================================================================

    def _analyze_impact_verbs(
        self,
        text: str,
    ) -> tuple[int, List[str]]:
        """
        Detect weak/passive action verbs.
        """

        matches = WEAK_VERBS_REGEX.findall(text)

        if not matches:
            return 0, []

        detected = sorted(
            {
                (
                    match
                    if isinstance(match, str)
                    else next(
                        (
                            item
                            for item in match
                            if item
                        ),
                        "",
                    )
                ).lower()
                for match in matches
            }
            - {""}
        )

        penalty_per_occurrence = PENALTY_WEIGHTS.get(
            "weak_verb_per_occurrence",
            3,
        )

        max_penalty = PENALTY_WEIGHTS.get(
            "max_weak_verb_penalty",
            15,
        )

        penalty = min(
            max_penalty,
            len(matches) * penalty_per_occurrence,
        )

        return penalty, detected

    # =========================================================================
    # FORMATTING
    # =========================================================================

    def _analyze_formatting_artifacts(
        self,
        text: str,
    ) -> tuple[int, List[str]]:
        """
        Detect ATS-unfriendly formatting artifacts.
        """

        issues: List[str] = []
        penalty = 0

        if (
            FORMATTING_ARTIFACT_PATTERNS["table_pipes"].search(text)
            or FORMATTING_ARTIFACT_PATTERNS["html_tables"].search(text)
        ):
            issues.append("tables/columns detected")

            penalty += PENALTY_WEIGHTS.get(
                "table_penalty",
                15,
            )

        if FORMATTING_ARTIFACT_PATTERNS["html_images"].search(text):
            issues.append("images/diagrams detected")

            penalty += PENALTY_WEIGHTS.get(
                "image_column_penalty",
                15,
            )

        if FORMATTING_ARTIFACT_PATTERNS["multi_column_tabs"].search(text):
            issues.append("multi-column tab spacing")
            penalty += 5

        max_penalty = PENALTY_WEIGHTS.get(
            "max_formatting_penalty",
            25,
        )

        return min(max_penalty, penalty), issues

    # =========================================================================
    # BREVITY
    # =========================================================================

    def _analyze_brevity(
        self,
        text: str,
    ) -> tuple[int, List[str]]:
        """
        Analyze resume content density.

        Explicit bullets are preferred. If no explicit bullets are found,
        achievement statements are used.
        """

        issues: List[str] = []

        bullets = self._extract_bullets(text)

        if not bullets:
            bullets = self._extract_achievement_bullets(text)

        words = text.split()

        penalty = 0

        # Avoid making one condition automatically imply the other.
        if len(words) < 150:
            issues.append(
                "resume contains fewer than 150 words"
            )

            penalty += PENALTY_WEIGHTS.get(
                "low_bullet_count_penalty",
                15,
            )

        elif len(bullets) < 3:
            issues.append(
                "fewer than 3 achievement/responsibility bullets detected"
            )

            penalty += min(
                8,
                PENALTY_WEIGHTS.get(
                    "low_bullet_count_penalty",
                    15,
                ),
            )

        invalid_length_count = 0

        for bullet in bullets:
            word_count = len(bullet.split())

            if word_count < 5 or word_count > 45:
                invalid_length_count += 1

        if invalid_length_count > 0:
            issues.append(
                f"{invalid_length_count} bullet(s) have "
                f"non-standard length (<5 or >45 words)"
            )

            penalty += min(
                10,
                invalid_length_count
                * PENALTY_WEIGHTS.get(
                    "invalid_bullet_length_penalty",
                    2,
                ),
            )

        max_penalty = PENALTY_WEIGHTS.get(
            "max_brevity_penalty",
            15,
        )

        return min(max_penalty, penalty), issues

    # =========================================================================
    # KEYWORD EXTRACTION
    # =========================================================================

    def _extract_keywords(
        self,
        text: str,
    ) -> Set[str]:
        """
        Extract meaningful normalized keywords.
        """

        raw_tokens = re.findall(
            r"\b[a-zA-Z0-9+#.-]+\b",
            text.lower(),
        )

        keywords: Set[str] = set()

        for token in raw_tokens:
            cleaned = token.strip(".-")

            if (
                len(cleaned) >= 2
                and cleaned not in STOP_WORDS
            ):
                keywords.add(cleaned)

        return keywords

    # =========================================================================
    # IMPROVEMENT ADVICE
    # =========================================================================

    def _generate_improvement_advice(
        self,
        resume_text: str,
        missing_skills: Set[str],
        required_skills: Set[str],
        penalties: Dict[str, Any],
        structure: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate grounded recommendations tied to actual score signals.
        """

        advice: List[Dict[str, Any]] = []

        # ---------------------------------------------------------------------
        # Missing required skills
        # ---------------------------------------------------------------------

        missing_required = sorted(
            missing_skills & required_skills
        )

        if missing_required:
            skills = ", ".join(
                skill.title()
                for skill in missing_required[:5]
            )

            advice.append({
                "category": "required_skills",
                "priority": "high",
                "suggestion": (
                    f"If supported by your real experience, add evidence "
                    f"for {skills} to relevant experience or project bullets. "
                    f"Do not add unsupported skills."
                ),
                "score_signal": "required_skill_coverage",
                "target": missing_required[:5],
            })

        # ---------------------------------------------------------------------
        # Weak verbs
        # ---------------------------------------------------------------------

        weak_verbs = penalties.get(
            "weak_verbs_found"
        ) or []

        if weak_verbs:
            advice.append({
                "category": "impact_language",
                "priority": "medium",
                "suggestion": (
                    f"Rewrite bullets containing "
                    f"{', '.join(weak_verbs[:3])} with accurate "
                    f"ownership-oriented language while preserving "
                    f"the original meaning."
                ),
                "score_signal": "impact_verbs",
                "target": weak_verbs[:3],
            })

        # ---------------------------------------------------------------------
        # Quantified impact
        # ---------------------------------------------------------------------

        if penalties.get("metrics", 0) > 0:
            metric_issues = penalties.get(
                "metric_issues"
            ) or []

            if metric_issues:
                suggestion = (
                    f"{metric_issues[0]}. Add truthful measurable "
                    f"outcomes only to achievement bullets that currently "
                    f"lack evidence. Existing quantified bullets do not "
                    f"need additional numbers."
                )
            else:
                suggestion = (
                    "Add truthful measurable outcomes to relevant "
                    "achievement bullets when real metrics are available."
                )

            advice.append({
                "category": "quantified_impact",
                "priority": "medium",
                "suggestion": suggestion,
                "score_signal": "metrics",
                "target": metric_issues,
            })

        # ---------------------------------------------------------------------
        # Structure
        # ---------------------------------------------------------------------

        missing_headings = structure.get(
            "missing_headings"
        ) or []

        if missing_headings:
            advice.append({
                "category": "resume_structure",
                "priority": "low",
                "suggestion": (
                    f"Use clear text headings for "
                    f"{', '.join(missing_headings[:3])}. "
                    f"Only add sections containing truthful content."
                ),
                "score_signal": "structure",
                "target": missing_headings[:3],
            })

        # ---------------------------------------------------------------------
        # Formatting
        # ---------------------------------------------------------------------

        if penalties.get("formatting", 0) > 0:
            advice.append({
                "category": "formatting",
                "priority": "high",
                "suggestion": (
                    "Replace ATS-unfriendly tables, images, or "
                    "multi-column spacing with a simple "
                    "single-column text layout."
                ),
                "score_signal": "formatting",
                "target": penalties.get(
                    "formatting_issues",
                    [],
                ),
            })

        # ---------------------------------------------------------------------
        # Brevity
        # ---------------------------------------------------------------------

        if penalties.get("brevity", 0) > 0:
            advice.append({
                "category": "content_density",
                "priority": "medium",
                "suggestion": (
                    "Strengthen the most relevant experience/project "
                    "bullets with action, technology, and truthful outcome "
                    "details while keeping each bullet concise."
                ),
                "score_signal": "brevity",
                "target": penalties.get(
                    "brevity_issues",
                    [],
                ),
            })

        return advice[:6]

    def _build_match_explanation(
        self,
        resume_text: str,
        job_description: str,
        match_score: int,
        matched_skills: Set[str],
        missing_skills: Set[str],
        required_skills: Set[str],
        preferred_skills: Set[str],
        structure: Dict[str, Any],
        penalties: Dict[str, Any],
        coverage_score: float,
        density_score: float,
        achievement_bullets: List[str],
        quantified_bullets: List[str],
    ) -> Dict[str, Any]:
        """Build a deterministic, evidence-based dashboard explanation."""
        parse_warnings = structure.get("parse_warnings") or []
        format_score = max(
            0,
            100
            - min(100, penalties.get("formatting", 0) * 4)
            - min(30, len(parse_warnings) * 10),
        )
        style_score = max(
            0,
            100 - min(
                100,
                penalties.get("impact_verbs", 0) * 4
                + penalties.get("brevity", 0) * 2,
            ),
        )
        section_names = structure.get("detected_headings") or []
        missing_sections = structure.get("missing_headings") or []
        total_sections = len(section_names) + len(missing_sections)
        heading_score = (len(section_names) / total_sections * 100) if total_sections else 0
        contact = structure.get("contact") or {}
        contact_score = sum(
            bool(contact.get(field)) for field in ("email_detected", "phone_detected")
        ) / 2 * 100
        sections_score = round(heading_score * 0.8 + contact_score * 0.2)
        content_score = round(
            min(
                100,
                density_score * 55
                + (min(1.0, len(quantified_bullets) / max(1, len(achievement_bullets))) * 25)
                + (min(1.0, len(achievement_bullets) / 6) * 20),
            )
        )
        category_scores = {
            "content": content_score,
            "skills": round(max(0, min(100, coverage_score * 100))),
            "sections": sections_score,
            "style": style_score,
            "format": format_score,
        }

        matched = sorted(matched_skills)
        highlights = []
        if matched:
            highlights.append(f"Relevant skills matched: {', '.join(skill.title() for skill in matched[:4])}.")
        if required_skills and required_skills.issubset(matched_skills):
            highlights.append("All detected required technical skills are represented in the resume.")
        elif matched:
            highlights.append(f"The resume demonstrates {len(matched)} job-related technical skill(s) from the description.")
        if quantified_bullets:
            highlights.append(f"Detected measurable impact in {len(quantified_bullets)} achievement bullet(s).")
        elif achievement_bullets:
            highlights.append(f"Detected {len(achievement_bullets)} experience/project achievement bullet(s) to refine.")
        else:
            highlights.append("The resume contains candidate content that can be compared against the target role.")
        highlights = highlights[:3]
        while len(highlights) < 3:
            highlights.append("The ATS analysis completed without inventing candidate facts.")

        improvements = []
        missing_required = sorted(missing_skills & required_skills)
        missing_preferred = sorted(missing_skills & preferred_skills)
        if missing_required:
            improvements.append(f"If you have genuine experience with {', '.join(skill.title() for skill in missing_required[:3])}, add evidence to the relevant role or project.")
        elif missing_preferred:
            improvements.append(f"If supported by your background, add evidence for preferred skill(s): {', '.join(skill.title() for skill in missing_preferred[:3])}.")
        if penalties.get("metrics", 0):
            improvements.append("Add truthful measurable outcomes to remaining unquantified achievement bullets where real data is available.")
        elif penalties.get("impact_verbs", 0):
            improvements.append("Replace weak phrasing with accurate action-oriented language while preserving your actual level of ownership.")
        elif penalties.get("formatting", 0):
            improvements.append("Use a single-column layout with standard headings and no tables or image-dependent content.")
        else:
            improvements.append("Keep the strongest role-relevant evidence near the top and avoid adding unsupported keywords.")
        if penalties.get("brevity", 0) and len(improvements) < 3:
            improvements.append("Expand only the most relevant bullets with truthful scope, method, and outcome details.")
        if len(structure.get("missing_headings") or []) and len(improvements) < 3:
            improvements.append(f"Add only useful sections with real content, such as {', '.join(structure['missing_headings'][:2])}.")
        fallback_improvements = [
            "Keep the strongest role-relevant evidence near the top of the resume.",
            "Use standard section headings and concise bullets for reliable ATS parsing.",
            "Recalculate the score after edits and keep changes that improve evidence-based alignment.",
        ]
        for fallback in fallback_improvements:
            if len(improvements) >= 3:
                break
            if fallback not in improvements:
                improvements.append(fallback)

        improvements = list(dict.fromkeys(improvements))
        while len(improvements) < 3:
            improvements.append(f"Review the next highest-impact gap before making further edits ({len(improvements) + 1}).")

        matched_text = ", ".join(skill.title() for skill in matched[:4]) or "the detected requirements"
        gap_text = ", ".join(skill.title() for skill in missing_required[:3]) if missing_required else "the remaining role-specific requirements"
        overview = (
            f"The resume scores {match_score}% against the supplied job description, with strongest alignment in {matched_text}. "
            f"The main opportunity is to strengthen evidence for {gap_text}. "
            "Only changes supported by the candidate's actual background should be added."
        )
        return {
            "match_score": match_score,
            "overview": overview,
            "radar_chart": category_scores,
            "highlights": highlights,
            "improvements": improvements[:3],
        }

    # =========================================================================
    # SEMANTIC SIGNAL
    # =========================================================================

    async def _semantic_signal(
        self,
        resume_text: str,
        job_description: str,
    ) -> float:
        """
        Compute optional embedding similarity.

        Embeddings are intentionally optional so ATS scoring does not fail
        when the embedding provider is unavailable.
        """

        try:
            resume_vector, job_vector = await asyncio.gather(
                asyncio.to_thread(
                    get_embedding,
                    resume_text[:12000],
                ),
                asyncio.to_thread(
                    get_embedding,
                    job_description[:12000],
                ),
            )

            return cosine_similarity(
                resume_vector,
                job_vector,
            )

        except Exception:
            return 0.0

    # =========================================================================
    # MAIN ATS SCORE
    # =========================================================================

    def _calculate_ats_score(
        self,
        resume_text: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """
        Compute ATS score from job relevance and calibrated quality penalties.
        """

        if (
            not resume_text.strip()
            or not job_description.strip()
        ):
            return {
                "ats_score": 0,
                "overall_score": 0.0,
                "matched_skills": [],
                "missing_skills": [],
                "missing_keywords": [],
                "semantic_gaps": [],
                "actionable_feedback": (
                    "Please upload or enter a resume and target "
                    "job description to compute an ATS score."
                ),
                "penalties": {},
            }

        # =====================================================================
        # 1. TECHNICAL SKILL MATCHING
        # =====================================================================

        jd_skills = self._extract_technical_skills(
            job_description
        )

        resume_skills = self._extract_technical_skills(
            resume_text
        )

        required_skills, preferred_skills = (
            self._classify_job_skills(
                job_description,
                jd_skills,
            )
        )

        matched_skills = (
            jd_skills & resume_skills
        )

        missing_skills = (
            jd_skills - resume_skills
        )

        matched_required = (
            required_skills & resume_skills
        )

        matched_preferred = (
            preferred_skills & resume_skills
        )

        # =====================================================================
        # 2. SKILL COVERAGE SCORE
        # =====================================================================

        if jd_skills:

            required_ratio = (
                len(matched_required)
                / len(required_skills)
                if required_skills
                else 1.0
            )

            preferred_ratio = (
                len(matched_preferred)
                / len(preferred_skills)
                if preferred_skills
                else 1.0
            )

            weighted_coverage = (
                required_ratio * 0.75
                + preferred_ratio * 0.25
            )

            coverage_score = math.sqrt(
                max(0.0, min(1.0, weighted_coverage))
            )

        else:
            # No technical skills explicitly detected in JD.
            coverage_score = 0.85

        # =====================================================================
        # 3. ROLE KEYWORD RELEVANCE
        # =====================================================================

        jd_tokens = self._extract_keywords(
            job_description
        )

        skill_tokens: Set[str] = set()

        for skill in jd_skills:
            skill_tokens.update(
                self._extract_keywords(skill)
            )

        jd_role_tokens = (
            jd_tokens
            - skill_tokens
            - JOB_FILLER_WORDS
        )

        if jd_role_tokens:

            resume_tokens = self._extract_keywords(
                resume_text
            )

            matched_role_tokens = (
                jd_role_tokens & resume_tokens
            )

            density_score = (
                len(matched_role_tokens)
                / len(jd_role_tokens)
            )

            # Preserve original calibration idea.
            density_score = min(
                1.0,
                density_score * 1.5,
            )

        else:
            density_score = 0.85

        # =====================================================================
        # 4. BASE SCORE
        # =====================================================================

        base_score = (
            coverage_score * 65.0
            + density_score * 35.0
        )

        # =====================================================================
        # 5. QUALITY / ATS PENALTIES
        # =====================================================================

        (
            impact_penalty,
            weak_verbs,
        ) = self._analyze_impact_verbs(
            resume_text
        )

        (
            formatting_penalty,
            formatting_issues,
        ) = self._analyze_formatting_artifacts(
            resume_text
        )

        (
            brevity_penalty,
            brevity_issues,
        ) = self._analyze_brevity(
            resume_text
        )

        (
            metric_penalty,
            metric_issues,
        ) = self._analyze_metric_density(
            resume_text
        )

        raw_penalties = (
            impact_penalty
            + formatting_penalty
            + brevity_penalty
            + metric_penalty
        )

        # Keep penalty cap from original architecture.
        total_penalties = min(
            30,
            raw_penalties,
        )

        # =====================================================================
        # 6. STRUCTURE
        # =====================================================================

        structure = self._analyze_structure(
            resume_text
        )

        self._clean_structure_warnings(
            structure
        )

        # =====================================================================
        # 7. PENALTY DETAILS
        # =====================================================================

        achievement_bullets = (
            self._extract_achievement_bullets(
                resume_text
            )
        )

        quantified_bullets = [
            bullet
            for bullet in achievement_bullets
            if self._contains_metric(bullet)
        ]

        metric_ratio = (
            len(quantified_bullets)
            / len(achievement_bullets)
            if achievement_bullets
            else 0.0
        )

        penalty_details = {
            "impact_verbs": impact_penalty,
            "formatting": formatting_penalty,
            "brevity": brevity_penalty,
            "metrics": metric_penalty,

            "total_penalties": total_penalties,
            "raw_total_penalties": raw_penalties,

            "weak_verbs_found": weak_verbs,

            "formatting_issues": formatting_issues,
            "brevity_issues": brevity_issues,
            "metric_issues": metric_issues,

            # New diagnostic fields
            "achievement_bullet_count": len(
                achievement_bullets
            ),
            "quantified_bullet_count": len(
                quantified_bullets
            ),
            "metric_ratio": round(
                metric_ratio,
                4,
            ),
            "quantified_bullets": quantified_bullets[:10],
        }

        # =====================================================================
        # 8. IMPROVEMENT ADVICE
        # =====================================================================

        improvement_advice = (
            self._generate_improvement_advice(
                resume_text,
                missing_skills,
                required_skills,
                penalty_details,
                structure,
            )
        )

        # =====================================================================
        # 9. FINAL SCORE
        # =====================================================================

        calibrated_score = int(
            round(
                base_score
                - total_penalties
            )
        )

        calibrated_score = max(
            0,
            min(
                100,
                calibrated_score,
            ),
        )

        match_explanation = self._build_match_explanation(
            resume_text,
            job_description,
            calibrated_score,
            matched_skills,
            missing_skills,
            required_skills,
            preferred_skills,
            structure,
            penalty_details,
            coverage_score,
            density_score,
            achievement_bullets,
            quantified_bullets,
        )

        # =====================================================================
        # 10. ACTIONABLE FEEDBACK
        # =====================================================================

        feedback_lines: List[str] = []

        # ---------------------------------------------------------------------
        # Missing skills
        # ---------------------------------------------------------------------

        missing_required = (
            missing_skills
            & required_skills
        )

        if missing_required:
            top_missing = [
                skill.title()
                for skill in sorted(
                    missing_required
                )[:4]
            ]

            feedback_lines.append(
                "• Technical Skills Gap: "
                f"Missing required keywords "
                f"({', '.join(top_missing)}). "
                f"Add them only where supported by "
                f"your actual experience."
            )

        elif missing_skills:
            top_missing = [
                skill.title()
                for skill in sorted(
                    missing_skills
                )[:4]
            ]

            feedback_lines.append(
                "• Keyword Opportunity: "
                f"The job description also references "
                f"{', '.join(top_missing)}. "
                f"Include them only if you genuinely "
                f"have relevant experience."
            )

        # ---------------------------------------------------------------------
        # Weak verbs
        # ---------------------------------------------------------------------

        if weak_verbs:
            top_weak = [
                f"'{verb}'"
                for verb in weak_verbs[:3]
            ]

            feedback_lines.append(
                "• Action Verb Impact: "
                f"Detected weaker phrasing "
                f"({', '.join(top_weak)}). "
                f"Use accurate action-oriented wording "
                f"that reflects your real level of ownership."
            )

        # ---------------------------------------------------------------------
        # Metrics
        # ---------------------------------------------------------------------

        if metric_issues:
            feedback_lines.append(
                "• Quantified Impact Gap: "
                f"{metric_issues[0]}. "
                f"Add truthful metrics to unquantified "
                f"achievement bullets where measurable "
                f"results are available."
            )

        # ---------------------------------------------------------------------
        # Formatting
        # ---------------------------------------------------------------------

        if formatting_issues:
            feedback_lines.append(
                "• Formatting Warnings: "
                f"Detected non-standard elements "
                f"({', '.join(formatting_issues)}). "
                f"Prefer a simple single-column ATS-readable layout."
            )

        # ---------------------------------------------------------------------
        # Strong result
        # ---------------------------------------------------------------------

        if not feedback_lines:

            if quantified_bullets:
                feedback_lines.append(
                    "• Strong Match: Resume aligns well with "
                    "the job description and already includes "
                    "measurable achievement evidence."
                )
            else:
                feedback_lines.append(
                    "• Strong Keyword Match: Resume aligns well "
                    "with the job description. Maintain clear "
                    "achievement-focused bullets and ATS-friendly formatting."
                )

        actionable_feedback = "\n".join(
            feedback_lines[:4]
        )

        # =====================================================================
        # 11. SEMANTIC GAPS
        # =====================================================================

        semantic_gaps = [
            {
                "requirement": (
                    f"Missing Technical Skill: "
                    f"{skill.title()}"
                ),
                "similarity": 0.0,
            }
            for skill in sorted(
                missing_skills
            )
        ]

        # =====================================================================
        # 12. RESPONSE
        # =====================================================================

        return {
            "ats_score": calibrated_score,

            "match_explanation": match_explanation,

            "overall_score": (
                float(calibrated_score)
                / 100.0
            ),

            "matched_skills": sorted(
                matched_skills
            ),

            "missing_skills": sorted(
                missing_skills
            ),

            "missing_keywords": sorted(
                missing_skills
            ),

            "semantic_gaps": semantic_gaps,

            "semantic_similarity": 0.0,

            "required_skills": sorted(
                required_skills
            ),

            "preferred_skills": sorted(
                preferred_skills
            ),

            "matched_required_skills": sorted(
                matched_required
            ),

            "matched_preferred_skills": sorted(
                matched_preferred
            ),

            "skill_evidence": self._skill_evidence(
                resume_text,
                matched_skills,
            ),

            "score_components": {
                "skill_coverage": round(
                    coverage_score,
                    4,
                ),

                "role_keyword_density": round(
                    density_score,
                    4,
                ),

                "base_score": round(
                    base_score,
                    2,
                ),

                "penalty_total": (
                    total_penalties
                ),

                "achievement_bullet_count": len(
                    achievement_bullets
                ),

                "quantified_bullet_count": len(
                    quantified_bullets
                ),

                "metric_ratio": round(
                    metric_ratio,
                    4,
                ),
            },

            "structure": structure,

            "improvement_advice": (
                improvement_advice
            ),

            "actionable_feedback": (
                actionable_feedback
            ),

            "penalties": (
                penalty_details
            ),

            "quick_fixes": self.generate_quick_fixes(
                resume_text,
                job_description,
                {
                    "impact_verbs": impact_penalty,
                    "formatting": formatting_penalty,
                    "brevity": brevity_penalty,
                    "metrics": metric_penalty,

                    "weak_verbs_found": weak_verbs,

                    "formatting_issues": formatting_issues,
                    "brevity_issues": brevity_issues,
                    "metric_issues": metric_issues,
                },
            ),
        }

    # =========================================================================
    # CACHE
    # =========================================================================

    @lru_cache(maxsize=256)
    def _calculate_ats_score_cached(
        self,
        resume_text: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """
        Cache deterministic ATS results.
        """

        return self._calculate_ats_score(
            resume_text,
            job_description,
        )

    def calculate_ats_score(
        self,
        resume_text: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """
        Return deep copy so callers cannot mutate cached results.
        """

        return copy.deepcopy(
            self._calculate_ats_score_cached(
                resume_text,
                job_description,
            )
        )

    # =========================================================================
    # QUICK FIXES
    # =========================================================================

    def generate_quick_fixes(
        self,
        resume_text: str,
        job_description: str,
        penalties: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Return up to three interactive score improvement suggestions.
        """

        if (
            not resume_text.strip()
            or not job_description.strip()
        ):
            return []

        if penalties is None:
            penalties = (
                self.calculate_ats_score(
                    resume_text,
                    job_description,
                )
                .get(
                    "penalties",
                    {},
                )
            )

        ranked = sorted(
            [
                (
                    "impact_verbs",
                    penalties.get(
                        "impact_verbs",
                        0,
                    ),
                    "Weak Verbs",
                ),
                (
                    "metrics",
                    penalties.get(
                        "metrics",
                        0,
                    ),
                    "Missing Metrics",
                ),
                (
                    "formatting",
                    penalties.get(
                        "formatting",
                        0,
                    ),
                    "Formatting Density",
                ),
                (
                    "brevity",
                    penalties.get(
                        "brevity",
                        0,
                    ),
                    "Brevity Issues",
                ),
            ],
            key=lambda item: item[1],
            reverse=True,
        )

        fixes: List[Dict[str, Any]] = []

        for (
            penalty_type,
            points,
            label,
        ) in ranked:

            if points <= 0:
                continue

            fix = self._build_quick_fix(
                penalty_type,
                resume_text,
                points,
                label,
                penalties,
            )

            if fix:
                fixes.append(fix)

            if len(fixes) >= 3:
                break

        return fixes

    def _build_quick_fix(
        self,
        penalty_type: str,
        resume_text: str,
        points: int,
        label: str,
        penalties: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        """
        Build one safe quick-fix recommendation.

        This function never invents quantitative outcomes.
        """

        # =====================================================================
        # WEAK VERBS
        # =====================================================================

        if penalty_type == "impact_verbs":

            weak_verbs = penalties.get(
                "weak_verbs_found"
            ) or []

            for verb in weak_verbs:

                pattern = re.compile(
                    re.escape(verb),
                    re.IGNORECASE,
                )

                match = pattern.search(
                    resume_text
                )

                if not match:
                    continue

                replacement = (
                    STRONG_VERB_REPLACEMENTS.get(
                        verb.lower(),
                        "Led",
                    )
                )

                updated = (
                    resume_text[:match.start()]
                    + replacement
                    + resume_text[match.end():]
                )

                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,
                    "suggestion": (
                        f'Consider replacing '
                        f'"{match.group()}" with '
                        f'"{replacement}" if it accurately '
                        f'reflects your contribution.'
                    ),
                    "find_text": match.group(),
                    "replace_text": replacement,
                    "updated_resume": updated,
                }

            for verb in WEAK_ACTION_VERBS:

                pattern = re.compile(
                    r"(?<!\w)"
                    + re.escape(verb)
                    + r"(?!\w)",
                    re.IGNORECASE,
                )

                match = pattern.search(
                    resume_text
                )

                if not match:
                    continue

                replacement = (
                    STRONG_VERB_REPLACEMENTS.get(
                        verb.lower(),
                        "Led",
                    )
                )

                updated = (
                    resume_text[:match.start()]
                    + replacement
                    + resume_text[match.end():]
                )

                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,
                    "suggestion": (
                        f'Consider replacing '
                        f'"{match.group()}" with '
                        f'"{replacement}" if accurate.'
                    ),
                    "find_text": match.group(),
                    "replace_text": replacement,
                    "updated_resume": updated,
                }

        # =====================================================================
        # METRICS
        # =====================================================================

        if penalty_type == "metrics":

            bullets = (
                self._extract_achievement_bullets(
                    resume_text
                )
            )

            for bullet in bullets:

                # Do NOT recommend adding a metric
                # to a bullet that already contains one.
                if self._contains_metric(
                    bullet
                ):
                    continue

                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,

                    "suggestion": (
                        "This achievement bullet does not contain "
                        "a measurable outcome. Add a truthful metric "
                        "such as latency, accuracy, users, throughput, "
                        "cost, time saved, reliability, dataset size, "
                        "or another real result if one is available."
                    ),

                    "find_text": bullet,
                    "replace_text": "",

                    # Frontend can open a user input
                    # instead of automatically rewriting.
                    "requires_user_value": True,
                }

        # =====================================================================
        # FORMATTING
        # =====================================================================

        if penalty_type == "formatting":

            if "|" in resume_text:

                updated = resume_text.replace(
                    "|",
                    " ",
                )

                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,

                    "suggestion": (
                        "Remove table-style pipe separators "
                        "for a simpler ATS-readable layout."
                    ),

                    "find_text": "|",
                    "replace_text": " ",
                    "updated_resume": updated,
                }

            if "\t\t" in resume_text:

                updated = resume_text.replace(
                    "\t\t",
                    " ",
                )

                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,

                    "suggestion": (
                        "Replace multi-column tab spacing "
                        "with normal single-column spacing."
                    ),

                    "find_text": "\t\t",
                    "replace_text": " ",
                    "updated_resume": updated,
                }

        # =====================================================================
        # BREVITY
        # =====================================================================

        if penalty_type == "brevity":

            bullets = self._extract_bullets(
                resume_text
            )

            if not bullets:
                bullets = (
                    self._extract_achievement_bullets(
                        resume_text
                    )
                )

            for bullet in bullets:

                if len(
                    bullet.split()
                ) >= 8:
                    continue

                # IMPORTANT:
                # Do not automatically fabricate business impact.
                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,

                    "suggestion": (
                        "This bullet is very short. Add truthful "
                        "context about the action, technology, scope, "
                        "or result rather than inserting generic "
                        "business-impact language."
                    ),

                    "find_text": bullet,
                    "replace_text": "",
                    "requires_user_value": True,
                }

        return None

    # =========================================================================
    # PUBLIC WRAPPER
    # =========================================================================

    def calculate_score(
        self,
        resume_text: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """
        Compatibility wrapper.
        """

        return self.calculate_ats_score(
            resume_text,
            job_description,
        )

    # =========================================================================
    # HYBRID / SEMANTIC SCORE
    # =========================================================================

    async def combined_score(
        self,
        resume_text: str,
        job_description: str,
    ) -> ATSScore:
        """
        Return deterministic ATS score optionally blended with semantic
        embedding similarity.
        """

        details = self.calculate_ats_score(
            resume_text,
            job_description,
        )

        try:
            configured_weight = float(
                os.getenv(
                    "ATS_SEMANTIC_WEIGHT",
                    "0",
                )
            )

        except (TypeError, ValueError):
            configured_weight = 0.0

        semantic_weight = min(
            0.25,
            max(
                0.0,
                configured_weight,
            ),
        )

        if (
            semantic_weight
            and resume_text.strip()
            and job_description.strip()
        ):

            semantic_score = (
                await self._semantic_signal(
                    resume_text,
                    job_description,
                )
            )

            legacy_score = float(
                details["overall_score"]
            )

            details["semantic_similarity"] = (
                semantic_score
            )

            details["overall_score"] = (
                (1.0 - semantic_weight)
                * legacy_score
                + semantic_weight
                * semantic_score
            )

            details["ats_score"] = int(
                round(
                    details["overall_score"]
                    * 100
                )
            )

        return ATSScore(
            score=details["overall_score"],

            method=(
                "hybrid_weighted_skill_overlap"
                if semantic_weight
                else "weighted_skill_overlap"
            ),

            details=details,
        )

    # =========================================================================
    # LANGGRAPH WORKFLOW
    # =========================================================================

    async def run(
        self,
        state: AgentState,
    ) -> AgentState:
        """
        Write ATS analysis and score into shared workflow state.
        """

        resume = (
            state.get("optimized_resume")
            or state.get("resume_text")
            or ""
        )

        job_desc = (
            state.get("job_description")
            or ""
        )

        score = await self.combined_score(
            resume,
            job_desc,
        )

        state["ats_score"] = score.score
        state["matching_score"] = score.score

        state.setdefault(
            "metadata",
            {},
        )["ats_analysis"] = score.details

        state["workflow_status"] = (
            "ats_analyzed"
        )

        return state
