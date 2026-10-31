import sys, asyncio
sys.path.insert(0, '.')
from src.agents.ats_engine import ATSEngine, COMMON_TECHNICAL_SKILLS, SKILL_ALIASES
from config.constants import WEAK_VERBS_REGEX, FORMATTING_ARTIFACT_PATTERNS

# Simulate a LaTeX-extracted resume text (with | pipes from right-aligned dates)
latex_resume = r"""Aaryan Johri
82aaryan@gmail.com | 8356952048 | github.com/aaryanideas28

EDUCATION
Veermata Jijabai Technological Institute (VJTI)                Mumbai, India
B.Tech in Computer Engineering                                 May 2029

EXPERIENCE
Kaizen.AI - AI Resume Automation Platform | Python, FastAPI, LangGraph    Sept 2024 - Present
- Contributed to building an AI-powered resume platform using FastAPI and LangGraph
- Collaborated with 3+ LLM pipelines to automate resume tailoring
- Participated in architecting multi-agent orchestration with MCP protocol

PROJECTS
OR-Tools Route Optimizer | Python, OR-Tools, FastAPI              2024
- Reduced delivery cost by 22% using Google OR-Tools VRP solver
- Built REST API with FastAPI serving 500+ daily queries

Tree-Sitter Code Parser | Python, Tree-Sitter, WebSockets         2024
- Parsed 10+ programming language ASTs with Tree-Sitter
- Exposed real-time parsing via WebSocket API

TECHNICAL SKILLS
Languages: Python, SQL, Bash
Frameworks: FastAPI, LangGraph, pytest
Tools: Docker, Git, CI/CD
AI/ML: RAG, LLM, Hugging Face transformers
"""

jd = """Software Engineer Intern - AI/Backend
We are looking for a motivated intern to join our team.
Requirements:
- Python, FastAPI, REST APIs
- Experience with Docker, CI/CD
- Familiarity with LLM, RAG, Transformers
- pytest, Git
- WebSockets a plus
Responsibilities:
- Build and maintain backend services
- Work on AI pipelines
- Write tests and documentation
"""

e = ATSEngine()
result = e.calculate_ats_score(latex_resume, jd)
print("=== BEFORE FIX DEBUG ===")
print(f"ATS Score: {result['ats_score']}")
print(f"Matched skills: {sorted(result['matched_skills'])}")
print(f"Missing skills: {sorted(result['missing_skills'])}")
print(f"Penalties: {result['penalties']}")
print(f"Structure warnings: {result['structure']['parse_warnings']}")
print()

print("=== WEAK VERB CHECK ===")
found = WEAK_VERBS_REGEX.findall(latex_resume)
print(f"Weak verbs found in resume: {found}")
print()

print("=== FORMAT CHECK ===")
for k, v in FORMATTING_ARTIFACT_PATTERNS.items():
    m = v.findall(latex_resume)
    if m:
        print(f"  {k} TRIGGERED: {m[:3]}")
    else:
        print(f"  {k}: clean")
print()

print("=== SKILLS MISSING FROM VOCAB ===")
missing_from_vocab = ['langgraph', 'or-tools', 'tree-sitter', 'mcp', 'websockets', 'websocket', 'pytest', 'rest', 'ci/cd']
for s in missing_from_vocab:
    print(f"  '{s}': in_vocab={s in COMMON_TECHNICAL_SKILLS}")

