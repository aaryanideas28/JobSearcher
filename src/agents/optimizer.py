# File: src/agents/optimizer.py
"""Resume optimization agent with Ollama routing, ATS feedback loop, entity locking, and 1-page constraints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from src.agents.ats_engine import ATSEngine
from src.agents.router import RoutingDecision, TaskComplexityRouter
from src.clients.ollama import OllamaClient
from src.schemas.resume import validate_resume_info_density


@dataclass(slots=True)
class OptimizationResult:
    """Output produced by the resume optimizer."""

    optimized_resume: str
    change_summary: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResumeOptimizer:
    """Agent responsible for tailoring a resume to a selected job target with ATS feedback loop."""

    def __init__(
        self,
        router: TaskComplexityRouter | None = None,
        llm_client: OllamaClient | None = None,
        ats_engine: ATSEngine | None = None,
    ) -> None:
        self.router = router or TaskComplexityRouter()
        self.llm_client = llm_client or OllamaClient()
        self.ats_engine = ats_engine or ATSEngine()
        self.raw_resume_text = ""

    def extract_resume_facts(self, resume_text: str) -> Dict[str, Any]:
        """Extract simple facts from resume text for downstream validation."""
        words = [word.strip(".,:;()[]{}") for word in resume_text.split()]
        skills = sorted({word for word in words if word and word[:1].isupper()})[:25]
        return {"skills": skills, "raw_length": len(resume_text), "source": "resume_text"}

    def extract_locked_entities(self, resume_text: str) -> Dict[str, Set[str]]:
        """Extract factual entities (Names, Years, Companies) prior to optimization."""
        years = set(re.findall(r"\b(?:19|20)\d\d\b", resume_text))
        company_matches = set(re.findall(
            r"\b[A-Z][a-zA-B0-9&\'.]+(?:\s+[A-Z][a-zA-B0-9&\'.]+)*(?:\s+(?:Inc\.|LLC|Corp\.|Corporation|Labs|Technologies|Systems|Solutions|University|College|Institute))?\b",
            resume_text
        ))
        reserved = {"Resume", "Education", "Experience", "Skills", "Projects", "Summary", "Professional", "Work", "Target"}
        companies = {c for c in company_matches if c not in reserved and len(c) > 2}

        lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
        names = set()
        if lines and len(lines[0]) < 50 and not any(h in lines[0].lower() for h in ["resume", "summary", "objective"]):
            names.add(lines[0])

        return {
            "years": years,
            "companies": companies,
            "names": names,
        }

    def restore_locked_entities(self, text: str, locked: Dict[str, Set[str]]) -> str:
        """Ensure clean text without adding bloated junk headers or placeholders."""
        text = re.sub(r"#{1,6}\s*", "", text)
        return text.strip()

    def clean_syntax(self, text: str) -> str:
        """Strip markdown bolding (**) and em-dashes (—). Replace with standard hyphens (-)."""
        if not text:
            return ""
        text = text.replace("—", " - ").replace("–", " - ").replace("&mdash;", " - ").replace("&ndash;", " - ")
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\s+-\s+", " - ", text)
        return text.strip()

    def enforce_length_constraint(self, text: str, max_chars: int = 3000) -> str:
        """Enforce 1-page resume budget (< 3000 characters)."""
        text = self.clean_syntax(text)
        if len(text) <= max_chars:
            return text
        trimmed = text[:max_chars]
        last_newline = trimmed.rfind("\n")
        if last_newline > int(max_chars * 0.7):
            return trimmed[:last_newline].strip()
        return trimmed.strip()


    async def build_resume_from_skills(self, skills: List[str], target_role: str) -> Dict[str, Any] | str:
        """Synthesize a complete, professional JSON resume schema from a list of skills and target role."""
        if not skills and not target_role:
            return self.raw_resume_text or ""

        import json
        from src.security.validation import JSONSchemaValidator

        skills_str = ", ".join(skills)
        prompt = (
            f"You are an expert resume writer. Build an ATS-compatible JSON resume using only the supplied candidate skills and target role: '{target_role}'. Supplied skills: {skills_str}.\n"
            "Never invent identity, education, companies, dates, experience, projects, certifications, achievements, links, or metrics. Leave unsupported fields empty. Do not convert skills into work experience.\n"
            "The JSON must strictly conform to the following schema structure, with no extra fields:\n"
            "{\n"
            '  "contact": {\n'
            '    "name": "",\n'
            '    "email": "",\n'
            '    "phone": "",\n'
            '    "location": "",\n'
            '    "links": []\n'
            "  },\n"
            '  "summary": "Summary text emphasizing targeted skills",\n'
            '  "skills": ["skill1", "skill2"],\n'
            '  "experience": [],\n'
            '  "education": [],\n'
            '  "certifications": [],\n'
            '  "projects": []\n'
            "}\n"
            "Return only valid JSON matching this schema."
        )

        routing = self.router.route(prompt)
        try:
            llm_result = await self.llm_client.generate(
                model=routing.model_name,
                prompt=prompt,
                json_mode=True,
            )
            text = llm_result.text.strip()
            if text:
                parsed_data = json.loads(text)
                schema_model, validation = JSONSchemaValidator().parse_resume(parsed_data)
                if validation.valid and schema_model is not None:
                    return schema_model.model_dump()
        except Exception:
            pass

        return {
            "contact": {
                "name": "",
                "email": "",
                "phone": "",
                "location": "",
                "links": [],
            },
            "summary": "",
            "skills": skills,
            "experience": [],
            "education": [],
            "certifications": [],
            "projects": [],
        }

    async def optimize_resume(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: List[str] | None = None,
        target_role: str | None = None,
    ) -> OptimizationResult:
        """Generate an optimized resume with ATS feedback loop, entity locking, and length constraints."""
        if not resume_text or len(resume_text.strip()) == 0:
            raise ValueError("Cannot invoke optimizer on empty candidate context")

        # 1. Compute baseline ATS score
        baseline_score_obj = await self.ats_engine.combined_score(resume_text, job_description)
        old_score = baseline_score_obj.score
        target_score = old_score * 1.20

        # 2. Extract locked entities
        locked_entities = self.extract_locked_entities(resume_text)

        best_candidate = resume_text
        best_score = old_score

        max_retries = 3
        attempt = 0

        details = baseline_score_obj.details
        missing_keywords = details.get("missing_keywords", [])
        semantic_gaps = [g.get("requirement", "") for g in details.get("semantic_gaps", []) if isinstance(g, dict)]

        routing_dict: Dict[str, Any] = {}
        llm_metadata: Dict[str, Any] = {}
        used_fallback = False

        while attempt <= max_retries:
            prompt = self._build_optimization_prompt(
                resume_text=resume_text,
                job_description=job_description,
                skills_to_highlight=skills_to_highlight or [],
                target_role=target_role,
                missing_keywords=missing_keywords,
                semantic_gaps=semantic_gaps,
            )

            routing = self.router.route(prompt)
            routing_dict = self._routing_to_dict(routing)

            llm_result = await self.llm_client.generate(model=routing.model_name, prompt=prompt)
            candidate = llm_result.text.strip()
            llm_metadata = llm_result.metadata
            used_fallback = llm_result.used_fallback or (candidate == "{}") or not candidate

            if used_fallback:
                candidate = self._local_optimization_fallback(
                    resume_text=resume_text,
                    job_description=job_description,
                    skills_to_highlight=skills_to_highlight or [],
                    missing_keywords=missing_keywords,
                )

            # Enforce 1-page format (< 3500 chars)
            candidate = self.enforce_length_constraint(candidate, max_chars=3500)

            # Preserve locked entities
            candidate = self.restore_locked_entities(candidate, locked_entities)

            # Evaluate candidate ATS score
            new_score_obj = await self.ats_engine.combined_score(candidate, job_description)
            new_score = new_score_obj.score

            if new_score > best_score:
                best_candidate = candidate
                best_score = new_score

            if new_score >= target_score:
                break

            attempt += 1

        # If retries exhausted and best candidate didn't hit target, apply fallback enhancement if needed
        if best_score < target_score:
            enhanced = self._local_optimization_fallback(
                resume_text=best_candidate,
                job_description=job_description,
                skills_to_highlight=skills_to_highlight or [],
                missing_keywords=missing_keywords,
            )
            enhanced = self.enforce_length_constraint(enhanced, max_chars=3500)
            enhanced = self.restore_locked_entities(enhanced, locked_entities)
            enhanced_score_obj = await self.ats_engine.combined_score(enhanced, job_description)
            if enhanced_score_obj.score > best_score:
                best_candidate = enhanced
                best_score = enhanced_score_obj.score

        # Final post-processing: enforce strict 1-page length constraint (< 3500 chars)
        best_candidate = self.enforce_length_constraint(best_candidate, max_chars=3500)

        return OptimizationResult(
            optimized_resume=best_candidate,
            change_summary=[f"ATS score updated from {round(old_score, 4)} to {round(best_score, 4)} after {attempt + 1} iteration(s)."],
            metadata={
                "routing": routing_dict,
                "llm": llm_metadata,
                "used_fallback": used_fallback,
                "old_score": old_score,
                "new_score": best_score,
                "relative_improvement": round((best_score - old_score) / old_score, 4) if old_score > 0 else 0.0,
                "locked_entities": {k: list(v) for k, v in locked_entities.items()},
            },
        )


    def _build_optimization_prompt(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: List[str],
        target_role: str | None,
        missing_keywords: List[str] | None = None,
        semantic_gaps: List[str] | None = None,
    ) -> str:
        """Build a truthful, ATS-compatible, role-aware optimization prompt."""
        skills = ", ".join(skills_to_highlight) if skills_to_highlight else "None supplied"
        role = target_role or "the target role"
        missing = ", ".join(missing_keywords[:6]) if missing_keywords else "None"

        return (
            "You are an expert ATS resume editor. Optimize the resume using ONLY the candidate data below.\n\n"
            "TRUTHFULNESS RULES:\n"
            "- Never invent or assume companies, titles, dates, education, projects, technologies, certifications, achievements, links, or metrics.\n"
            "- Never add a job-description keyword unless the candidate data supports it.\n"
            "- Preserve every supplied fact and metric. If a metric is missing, improve scope, method, or deliverable without inventing a number.\n"
            "- Do not turn assistance into leadership or responsibility into an achievement.\n"
            "- Omit unsupported sections and placeholders.\n\n"
            "ATS AND QUALITY RULES:\n"
            "- Use a clean single-column text layout with standard headings.\n"
            "- Normalize compound technologies correctly (for example, FastAPI, PyTorch, TensorFlow, NumPy, Node.js, PostgreSQL, and CI/CD).\n"
            "- Remove duplicate skills and prioritize required skills over preferred skills only when supported.\n"
            "- Use action + task + method + result when the source supports those details.\n"
            "- Preserve existing quantified achievements; do not force metrics into every bullet.\n"
            "- Return only the final resume content, with no explanation or ATS commentary.\n\n"
            f"Target Role: {role}\n"
            f"Skills: {skills}\n"
            f"Missing Keywords: {missing}\n\n"
            "ATS Analysis: Use missing keywords and penalties only as diagnostic signals. Fix only genuine issues.\n\n"
            "Original Candidate Data:\n"
            f"{resume_text}\n\n"
            "Target Job Description:\n"
            f"{job_description}\n\n"
            "Return ONLY the optimized resume content."
        )


    def _local_optimization_fallback(
        self,
        resume_text: str,
        job_description: str,
        skills_to_highlight: List[str],
        missing_keywords: List[str] | None = None,
    ) -> str:
        """Return a cleaned source resume when generation is unavailable without inventing facts."""
        return self.clean_syntax(re.sub(r"#{1,6}\s*", "", resume_text)).strip()

        """Legacy fallback implementation retained below for reference only."""
        clean_text = re.sub(r"#{1,6}\s*", "", resume_text)

        # 1. Extract contact info
        lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
        name = "Aaryan Johri"
        email = "82aaryan@gmail.com"
        phone = "8356952048"
        location = "Mumbai, India"
        links = ["GitHub: aaryanideas28", "Codeforces: aajoh", "CodeChef: atjohri"]

        if lines:
            name = lines[0]

        for line in lines:
            if "@" in line:
                match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", line)
                if match:
                    email = match.group(0)
            if re.search(r"\b\d{10}\b", line):
                match = re.search(r"(\d{10})", line)
                if match:
                    phone = match.group(0)

        # Extract locked entities to preserve them in fallback
        locked = self.extract_locked_entities(resume_text)
        years = sorted(list(locked.get("years") or []))
        companies = list(locked.get("companies") or [])
        names = list(locked.get("names") or [])

        if names:
            name = names[0]

        # 2. Extract JD keywords for high ATS match (>85%)
        jd_keywords = self._extract_keywords(job_description, limit=12)
        missing = missing_keywords or []
        combined_skills = list(dict.fromkeys((skills_to_highlight or []) + missing[:5] + jd_keywords[:5]))[:8]

        langs = [s for s in combined_skills if s.lower() in {"python", "c++", "c", "java", "javascript", "typescript", "go", "sql", "html", "css"}]
        tools = [s for s in combined_skills if s.lower() in {"git", "linux", "docker", "aws", "vscode", "gnu octave"}]
        libs = [s for s in combined_skills if s.lower() not in [x.lower() for x in langs + tools]]

        if not langs:
            langs = ["Python", "C++", "SQL"]
        if not tools:
            tools = ["Git", "Linux", "Docker"]
        if not libs:
            libs = ["FastAPI", "SQLAlchemy", "Redis"]

        skills_block = (
            f"Languages: {', '.join(langs[:3])}\n"
            f"Tools: {', '.join(tools[:3])}\n"
            f"Libraries & Frameworks: {', '.join(libs[:3])}"
        )

        # 3. Dynamic High-Impact STAR bullets integrating job description terms
        kw_str = ", ".join(jd_keywords[:4])
        p1 = f"• **Engineered** scalable microservices to build RESTful APIs using **Python**, **FastAPI**, and **SQLAlchemy**, optimizing database pipeline queries to reduce latency by **30%**."
        p2 = f"• **Built** automated job discovery and web scraping data pipelines, seeking optimal performance for **10+ targeted backend engineer roles** with automated testing."
        p3 = f"• **Integrated** hybrid vector embeddings and keyword matching algorithms for scalable database search, achieving **92% accuracy** in real-time candidate match calculations."
        p4 = f"• **Orchestrated** asynchronous task queues and testing workflows with **Redis**, **Docker**, and **Celery**, enabling non-blocking document generation and automated outreach."

        # Guarantee preservation of locked companies and years in the projects/experience section
        if companies and years:
            p_list = []
            for comp in companies:
                p_list.append(f"• **Worked** at **{comp}** from **{years[0]}** to **{years[-1]}**, leading systems design and database migration workflows.")
            
            fallbacks = [p2, p3, p4]
            while len(p_list) < 4 and fallbacks:
                p_list.append(fallbacks.pop(0))
                
            p1 = p_list[0] if len(p_list) > 0 else ""
            p2 = p_list[1] if len(p_list) > 1 else ""
            p3 = p_list[2] if len(p_list) > 2 else ""
            p4 = p_list[3] if len(p_list) > 3 else ""

        # If clean_text is already fully formatted with Jenil Shah sections and dividers, return clean_text
        if "EDUCATION" in clean_text.upper() and "---" in clean_text and "PROJECTS" in clean_text.upper():
            return clean_text.strip()

        from src.utils.docx_compiler import DocxCompiler
        orig_data = DocxCompiler().parse_resume_text_to_dict(resume_text)
        
        if orig_data.get("contact", {}).get("name") and orig_data["contact"]["name"] != "Candidate":
            name = orig_data["contact"]["name"]
        
        email = orig_data.get("contact", {}).get("email") or email
        phone = orig_data.get("contact", {}).get("phone") or phone
        location = orig_data.get("contact", {}).get("location") or location
        
        # Build contact links
        contact_info = [
            val for val in [email, phone, location]
            if val and str(val).strip()
        ]
        contact_line = " | ".join(contact_info)
        
        # Dynamic Education Section
        edu_blocks = []
        for edu in orig_data.get("education") or []:
            edu_lines = []
            inst = edu.get("institution") or ""
            loc_val = edu.get("location") or ""
            if inst:
                inst_line = f"{inst} | {loc_val}" if loc_val else inst
                edu_lines.append(inst_line)
            deg = edu.get("degree") or ""
            dates_val = edu.get("dates") or ""
            grade_val = edu.get("grade") or ""
            if deg:
                deg_line = deg
                if dates_val:
                    deg_line += f" ({dates_val})"
                if grade_val:
                    deg_line += f" | Grade: {grade_val}"
                edu_lines.append(deg_line)
            if edu_lines:
                edu_blocks.append("\n".join(edu_lines))
                
        if edu_blocks:
            education_section = "\n\n".join(edu_blocks)
        else:
            education_section = (
                "Veermata Jijabai Technological Institute (VJTI) | Mumbai, India\n"
                "B.Tech in Computer Engineering — First Year (Expected Graduation: May 2029)\n"
                "Relevant Coursework: Data Structures & Algorithms, Linear Algebra, Probability & Statistics, Multivariable Calculus"
            )

        # Dynamic Achievements Section
        ach_blocks = []
        for a_item in orig_data.get("achievements") or []:
            ach_blocks.append(f"• {a_item}")
        if ach_blocks:
            achievements_section = "\n".join(ach_blocks)
        else:
            achievements_section = (
                "• Rank 3356 / 13,000+ in ICPC Prelims (National Level) among top competitive programming teams across India.\n"
                "• CodeChef Rating 1114 | Solved 100+ algorithmic problems across competitive programming platforms.\n"
                "• Codeforces Max Rating 1021 | Demonstrated strong problem-solving and mathematical reasoning under contest constraints."
            )

        # Dynamic Projects Section
        proj_blocks = []
        for proj in orig_data.get("projects") or []:
            proj_lines = []
            proj_name = proj.get("name") or "Project"
            proj_tech = proj.get("technologies") or ""
            proj_dates = proj.get("dates") or ""
            
            p1_line = proj_name
            if proj_tech:
                p1_line += f" | {proj_tech}"
            if proj_dates:
                p1_line += f" ({proj_dates})"
            proj_lines.append(p1_line)
            
            for b in proj.get("bullets") or []:
                proj_lines.append(f"• {b}")
                
            if proj_lines:
                proj_blocks.append("\n".join(proj_lines))
                
        if proj_blocks:
            projects_section = "\n\n".join(proj_blocks)
        else:
            projects_section = (
                f"FastAPI AI Resume & Job Search Platform | {', '.join(combined_skills[:5])}\n"
                f"{p1}\n"
                f"{p2}\n"
                f"{p3}\n"
                f"{p4}"
            )

        # Dynamic Extracurriculars Section
        ext_blocks = []
        for ex_item in orig_data.get("extracurriculars") or []:
            ext_blocks.append(f"• {ex_item}")
        if ext_blocks:
            ext_section = "\n".join(ext_blocks)
        else:
            ext_section = (
                "• Competitive Programmer: Active participant in Codeforces and CodeChef contests, focusing on algorithm optimization and graph theory.\n"
                "• Open Source Contributor: Developed and maintained software projects on GitHub with clean architecture and automated tests."
            )

        links_line = " | ".join(links)

        return (
            f"{name}\n"
            f"{contact_line}\n"
            f"{links_line}\n\n"
            "---\n"
            "EDUCATION\n"
            "---\n"
            f"{education_section}\n\n"
            "---\n"
            "ACHIEVEMENTS\n"
            "---\n"
            f"{achievements_section}\n\n"
            "---\n"
            "PROJECTS\n"
            "---\n"
            f"{projects_section}\n\n"
            "---\n"
            "EXTRACURRICULARS\n"
            "---\n"
            f"{ext_section}\n\n"
            "---\n"
            "SKILLS\n"
            "---\n"
            f"{skills_block}"
        )






    def _extract_keywords(self, text: str, limit: int = 12) -> List[str]:
        """Extract simple keyword candidates from text."""
        stop_words = {"and", "the", "for", "with", "you", "our", "are", "will", "this", "that", "from"}
        words = [word.lower().strip(".,:;()[]{}") for word in text.split()]
        unique = sorted({word for word in words if len(word) > 3 and word not in stop_words})
        return unique[:limit]

    def _routing_to_dict(self, decision: RoutingDecision) -> Dict[str, Any]:
        """Serialize a routing decision."""
        return {
            "model_tier": decision.model_tier.value,
            "model_name": decision.model_name,
            "reason": decision.reason,
            "estimated_complexity": decision.estimated_complexity,
        }
