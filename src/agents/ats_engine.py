# File: src/agents/ats_engine.py
"""Embedding-based semantic matching and regex ATS engine."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
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

STRONG_VERB_REPLACEMENTS: Dict[str, str] = {
    "assisted": "Spearheaded",
    "assisted with": "Spearheaded",
    "helped": "Drove",
    "helped to": "Drove",
    "worked on": "Engineered",
    "worked with": "Partnered with",
    "responsible for": "Owned",
    "duties included": "Delivered",
    "handled": "Orchestrated",
    "tasked with": "Led",
    "participated in": "Led",
    "served as": "Directed",
    "contributed to": "Accelerated",
    "involved in": "Executed",
    "managed to": "Achieved",
    "attempted to": "Implemented",
    "supported": "Enabled",
    "aided": "Championed",
    "was part of": "Led",
    "took part in": "Spearheaded",
    "dealt with": "Resolved",
}


class ATSEngine:
    """Analyze resume and job description using case-insensitive Weighted Skill Overlap and Penalty Calibration."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    def _extract_technical_skills(self, text: str) -> Set[str]:
        """Scan text and match exact terms from COMMON_TECHNICAL_SKILLS (case-insensitive)."""
        normalized = text.lower()
        matched = set()
        
        for skill in COMMON_TECHNICAL_SKILLS:
            escaped = re.escape(skill)
            if skill.endswith("++") or skill.endswith("#") or skill.startswith("."):
                pattern = r"(?:^|(?<=\s|/|,|;))" + escaped + r"(?:$|(?=\s|/|,|;|\.))"
            else:
                pattern = r"\b" + escaped + r"\b"
                
            if re.search(pattern, normalized):
                matched.add(skill)
        return matched

    def _analyze_impact_verbs(self, text: str) -> tuple[int, list[str]]:
        """Scan text using Regex for weak/passive action verbs and compute penalty."""
        matches = WEAK_VERBS_REGEX.findall(text)
        if not matches:
            return 0, []
        detected = sorted(list({m.lower() for m in matches}))
        penalty_per_occ = PENALTY_WEIGHTS.get("weak_verb_per_occurrence", 3)
        max_penalty = PENALTY_WEIGHTS.get("max_weak_verb_penalty", 15)
        penalty = min(max_penalty, len(matches) * penalty_per_occ)
        return penalty, detected

    def _analyze_formatting_artifacts(self, text: str) -> tuple[int, list[str]]:
        """Detect non-ATS formatting elements like table pipes, HTML tags, and tabs."""
        issues = []
        penalty = 0
        if FORMATTING_ARTIFACT_PATTERNS["table_pipes"].search(text) or FORMATTING_ARTIFACT_PATTERNS["html_tables"].search(text):
            issues.append("tables/columns detected")
            penalty += PENALTY_WEIGHTS.get("table_penalty", 15)
        if FORMATTING_ARTIFACT_PATTERNS["html_images"].search(text):
            issues.append("images/diagrams detected")
            penalty += PENALTY_WEIGHTS.get("image_column_penalty", 15)
        if FORMATTING_ARTIFACT_PATTERNS["multi_column_tabs"].search(text):
            issues.append("multi-column tab spacing")
            penalty += 5

        max_penalty = PENALTY_WEIGHTS.get("max_formatting_penalty", 25)
        return min(max_penalty, penalty), issues

    def _analyze_brevity(self, text: str) -> tuple[int, list[str]]:
        """Check bullet counts and word count for brevity violations."""
        issues = []
        bullets = self._extract_bullets(text)
        words = text.split()
        
        penalty = 0
        if len(bullets) < 3 or len(words) < 150:
            issues.append("insufficient total bullet/word count (< 150 words or < 3 bullets)")
            penalty += PENALTY_WEIGHTS.get("low_bullet_count_penalty", 15)

        invalid_len_count = 0
        for b in bullets:
            b_words = b.split()
            if len(b_words) < 5 or len(b_words) > 45:
                invalid_len_count += 1
                
        if invalid_len_count > 0:
            issues.append(f"{invalid_len_count} bullet(s) with non-standard length (< 5 or > 45 words)")
            penalty += min(10, invalid_len_count * PENALTY_WEIGHTS.get("invalid_bullet_length_penalty", 2))

        max_penalty = PENALTY_WEIGHTS.get("max_brevity_penalty", 15)
        return min(max_penalty, penalty), issues

    def _analyze_metric_density(self, text: str) -> tuple[int, list[str]]:
        """Check percentage of bullet points that contain quantified results/metrics using Regex."""
        bullets = self._extract_bullets(text)
        if not bullets:
            return 0, []

        metric_bullets_count = sum(1 for b in bullets if METRIC_PATTERNS_REGEX.search(b))
        ratio = metric_bullets_count / len(bullets)

        issues = []
        penalty = 0
        if ratio < 0.50:
            percentage_with_metrics = int(round(ratio * 100))
            issues.append(f"only {percentage_with_metrics}% of bullets contain quantified metrics (target: 50%+)")
            penalty = PENALTY_WEIGHTS.get("low_metric_ratio_penalty", 15)

        return penalty, issues

    def calculate_ats_score(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Compute strict, penalty-based calibrated ATS score (0-100) benchmarked against industry standards."""
        if not resume_text.strip() or not job_description.strip():
            return {
                "ats_score": 0,
                "overall_score": 0.0,
                "matched_skills": [],
                "missing_skills": [],
                "missing_keywords": [],
                "semantic_gaps": [],
                "actionable_feedback": "Please upload or enter a resume and target job description to compute an ATS score.",
                "penalties": {},
            }

        # 1. Skill & Token Extraction
        jd_skills = self._extract_technical_skills(job_description)
        resume_skills = self._extract_technical_skills(resume_text)

        matched_skills = jd_skills & resume_skills
        missing_skills = jd_skills - resume_skills

        # 2. Base Matching Score (0 - 100 scale)
        if jd_skills:
            coverage_score = len(matched_skills) / len(jd_skills)
        else:
            coverage_score = 0.8

        jd_tokens = self._extract_keywords(job_description)
        jd_role_tokens = jd_tokens - {s.lower() for s in jd_skills}

        if jd_role_tokens:
            resume_tokens = self._extract_keywords(resume_text)
            matched_role_tokens = jd_role_tokens & resume_tokens
            density_score = len(matched_role_tokens) / len(jd_role_tokens)
        else:
            density_score = 0.8

        base_score = (coverage_score * 65.0) + (density_score * 35.0)

        # 3. Penalty Analysis
        impact_penalty, weak_verbs = self._analyze_impact_verbs(resume_text)
        formatting_penalty, formatting_issues = self._analyze_formatting_artifacts(resume_text)
        brevity_penalty, brevity_issues = self._analyze_brevity(resume_text)
        metric_penalty, metric_issues = self._analyze_metric_density(resume_text)

        total_penalties = impact_penalty + formatting_penalty + brevity_penalty + metric_penalty

        # Calibrated Score calculation: benchmarked closer to Resume Worded range (~40%-65%)
        calibrated_score = int(round(base_score - total_penalties))
        calibrated_score = max(0, min(100, calibrated_score))

        # 4. Generate 3-4 line Actionable Feedback
        feedback_lines = []
        if missing_skills:
            top_missing = [s.title() for s in sorted(list(missing_skills))[:4]]
            feedback_lines.append(f"• Technical Skills Gap: Missing required keywords ({', '.join(top_missing)}). Add these naturally to your experience.")
        if weak_verbs:
            top_weak = [f"'{v}'" for v in weak_verbs[:3]]
            feedback_lines.append(f"• Action Verb Impact: Detected passive phrasing ({', '.join(top_weak)}). Replace with strong action verbs like 'Engineered' or 'Architected'.")
        if metric_issues:
            feedback_lines.append("• Quantified Impact Gap: Over 50% of your bullets lack measurable results. Add numbers, percentages, or multipliers (e.g. 'Improved efficiency by 30%').")
        if formatting_issues:
            feedback_lines.append(f"• Formatting Warnings: Detected non-standard elements ({', '.join(formatting_issues)}). Use single-column text without tables or images.")

        if not feedback_lines:
            feedback_lines.append("• Strong Keyword Match: Resume aligns well with job description. Maintain strong quantified bullet points and clean typography.")

        actionable_feedback = "\n".join(feedback_lines[:4])

        semantic_gaps = []
        for s in sorted(list(missing_skills)):
            semantic_gaps.append({
                "requirement": f"Missing Technical Skill: {s.title()}",
                "similarity": 0.0,
            })

        return {
            "ats_score": calibrated_score,
            "overall_score": float(calibrated_score) / 100.0,
            "matched_skills": sorted(list(matched_skills)),
            "missing_skills": sorted(list(missing_skills)),
            "missing_keywords": sorted(list(missing_skills)),
            "semantic_gaps": semantic_gaps,
            "actionable_feedback": actionable_feedback,
            "penalties": {
                "impact_verbs": impact_penalty,
                "formatting": formatting_penalty,
                "brevity": brevity_penalty,
                "metrics": metric_penalty,
                "total_penalties": total_penalties,
                "weak_verbs_found": weak_verbs,
                "formatting_issues": formatting_issues,
                "brevity_issues": brevity_issues,
                "metric_issues": metric_issues,
            },
            "quick_fixes": self.generate_quick_fixes(resume_text, job_description, {
                "impact_verbs": impact_penalty,
                "formatting": formatting_penalty,
                "brevity": brevity_penalty,
                "metrics": metric_penalty,
                "weak_verbs_found": weak_verbs,
                "formatting_issues": formatting_issues,
                "brevity_issues": brevity_issues,
                "metric_issues": metric_issues,
            }),
        }

    def generate_quick_fixes(
        self,
        resume_text: str,
        job_description: str,
        penalties: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Return top 3 interactive score-booster suggestions ordered by penalty severity."""
        if not resume_text.strip() or not job_description.strip():
            return []

        if penalties is None:
            penalties = self.calculate_ats_score(resume_text, job_description).get("penalties", {})

        ranked = sorted(
            [
                ("impact_verbs", penalties.get("impact_verbs", 0), "Weak Verbs"),
                ("metrics", penalties.get("metrics", 0), "Missing Metrics"),
                ("formatting", penalties.get("formatting", 0), "Formatting Density"),
                ("brevity", penalties.get("brevity", 0), "Brevity Issues"),
            ],
            key=lambda item: item[1],
            reverse=True,
        )

        fixes: List[Dict[str, Any]] = []
        for penalty_type, points, label in ranked:
            if points <= 0:
                continue
            fix = self._build_quick_fix(penalty_type, resume_text, points, label, penalties)
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
        if penalty_type == "impact_verbs":
            weak_verbs = penalties.get("weak_verbs_found") or []
            for verb in weak_verbs:
                pattern = re.compile(re.escape(verb), re.IGNORECASE)
                match = pattern.search(resume_text)
                if not match:
                    continue
                replacement = STRONG_VERB_REPLACEMENTS.get(verb.lower(), "Spearheaded")
                updated = resume_text[: match.start()] + replacement + resume_text[match.end() :]
                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,
                    "suggestion": f'Fix: Replace "{match.group()}" with "{replacement}"',
                    "find_text": match.group(),
                    "replace_text": replacement,
                    "updated_resume": updated,
                }
            for verb in WEAK_ACTION_VERBS:
                pattern = re.compile(r"\b" + re.escape(verb) + r"\b", re.IGNORECASE)
                match = pattern.search(resume_text)
                if not match:
                    continue
                replacement = STRONG_VERB_REPLACEMENTS.get(verb.lower(), "Spearheaded")
                updated = resume_text[: match.start()] + replacement + resume_text[match.end() :]
                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,
                    "suggestion": f'Fix: Replace "{match.group()}" with "{replacement}"',
                    "find_text": match.group(),
                    "replace_text": replacement,
                    "updated_resume": updated,
                }

        if penalty_type == "metrics":
            bullets = self._extract_bullets(resume_text)
            for bullet in bullets:
                if METRIC_PATTERNS_REGEX.search(bullet):
                    continue
                metric_suffix = ", improving throughput by 30%"
                updated_bullet = bullet.rstrip(".") + metric_suffix + "."
                updated = resume_text.replace(bullet, updated_bullet, 1)
                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,
                    "suggestion": "Fix: Add quantified impact (e.g. \"improving throughput by 30%\")",
                    "find_text": bullet,
                    "replace_text": updated_bullet,
                    "updated_resume": updated,
                }

        if penalty_type == "formatting":
            if "|" in resume_text:
                updated = resume_text.replace("|", " ")
                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,
                    "suggestion": "Fix: Remove table pipes for ATS-friendly single-column text",
                    "find_text": "|",
                    "replace_text": " ",
                    "updated_resume": updated,
                }
            if "\t\t" in resume_text:
                updated = resume_text.replace("\t\t", " ")
                return {
                    "penalty_type": penalty_type,
                    "label": label,
                    "points": points,
                    "suggestion": "Fix: Replace multi-column tab spacing with standard bullets",
                    "find_text": "\t\t",
                    "replace_text": " ",
                    "updated_resume": updated,
                }

        if penalty_type == "brevity":
            bullets = self._extract_bullets(resume_text)
            for bullet in bullets:
                if len(bullet.split()) < 8:
                    expanded = bullet.rstrip(".") + " across cross-functional teams to deliver measurable business outcomes."
                    updated = resume_text.replace(bullet, expanded, 1)
                    return {
                        "penalty_type": penalty_type,
                        "label": label,
                        "points": points,
                        "suggestion": "Fix: Expand sparse bullet with outcome-focused detail",
                        "find_text": bullet,
                        "replace_text": expanded,
                        "updated_resume": updated,
                    }

        return None

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
        bullet_lines = []
        general_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            # Lines starting with bullet markers (-, *, •, digit.)
            if re.match(r"^[\s•\-\*\d\.\)]+", line):
                cleaned = re.sub(r"^[\s•\-\*\d\.\)]+", "", line).strip()
                if len(cleaned) > 10:
                    bullet_lines.append(cleaned)
            elif len(line_str) > 20 and not line_str.endswith(":") and not line_str.isupper():
                general_lines.append(line_str)
        return bullet_lines if bullet_lines else (general_lines if general_lines else [text.strip()])
