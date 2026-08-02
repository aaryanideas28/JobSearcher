# AI Resume Automation Platform

FastAPI, LangGraph, PostgreSQL, Redis, Celery, Ollama, and document-generation scaffold for an AI-assisted resume/job-search automation system.

## Architecture

The repository is organized around the platform layers shown in the project diagram:

- `src/api`: FastAPI routes for auth, resume versioning, HITL approvals, outreach dispatch, and health checks.
- `src/workflow`: LangGraph state orchestration and Celery queue workers.
- `src/agents`: Resume optimization, ATS scoring, job discovery, outreach drafting, and model routing agents.
- `src/security`: Prompt-injection, JSON schema, hallucination, and quality guardrails.
- `src/utils`: PDF compilation and resilient scraping helpers.
- `database`: SQLAlchemy models plus the raw PostgreSQL schema.
- `storage_workspace`: local templates and generated document workspace.

## Local Setup

Create a virtual environment and install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
 
Start PostgreSQL and Redis:

```powershell
docker compose up -d
```

Run the API (execute from the project root directory):

```powershell
uvicorn src.api.main:app --reload
```
Open:

- API health: `http://localhost:8000/health`
- Swagger docs: `http://localhost:8000/docs`

## Database

The app can create SQLAlchemy tables during local development:

```powershell
python -c "from database.connection import init_db; init_db()"
```
The equivalent PostgreSQL DDL lives in `database/schema.sql`.
http://localhost:8000/dashboard 

## Architecture & Scoring

Stratum utilizes a **Two-Page Platform Architecture** combined with a **Penalty-Based ATS Scoring System** benchmarked against leading commercial resume audit engines (e.g., Resume Worded):

### 1. Platform Architecture (Two-Page Flow)
- **Page 1 (Landing Page - `LandingPage.jsx`)**: The primary entry point featuring the signature **Deep Purple** brand theme (`#1a0b36` / `#260f54`), candidate transformation stories (Alex Chen & Sarah Jenkins), the **ATS Compliance Guide** (6 core rules), and a primary "Get Started" CTA.
- **Page 2 (Original Dashboard Engine)**: Routes exclusively from the "Get Started" CTA into the interactive intake dashboard for multi-step candidate profile intake, Tavily job search, penalty-based ATS scoring, human-in-the-loop (HITL) draft reviews, auto-expansion email outreach, and automated DOCX downloading.

### 2. Module 6: Strict Intake Guard & Validation
- **Intake Mode Validation (`validate_candidate_intake`)**:
  - **Unselected Mode**: Raises HTTP 400 (`"Please select an intake option..."`) when `intake_mode` is missing.
  - **Upload Mode Guard**: Raises HTTP 400 (`"No resume file detected..."`) when `intake_mode == 'upload'` but no file or parsed text is attached.
  - **Build-from-Scratch Guard**: Raises HTTP 400 (`"Incomplete resume form..."`) when required fields (`full_name`, `email`, `technical_skills`, `work_experience`/`projects`) are empty.
- **Workflow & Optimizer Guardrails**:
  - `process_intake` entry node validates state completeness, flagging `MISSING_INTAKE_DATA` errors for empty payloads.
  - `ResumeOptimizer` rejects empty candidate contexts (`ValueError("Cannot invoke optimizer on empty candidate context")`), ensuring hallucination-free generation.

### 3. Penalty-Based ATS Scoring Calibration
- **Realistic Calibration**: Previous optimistic scanners yielded artificially inflated scores (80%+), masking critical resume deficiencies. Stratum's calibrated scanner calculates a strict baseline score (typically **30% – 65%** for unoptimized resumes) to provide constructive, actionable feedback rather than false validation.
- **Penalty Deduction Categories**:
  - **Impact Verbs (-5 to -15 pts)**: Penalizes weak or passive verb phrasing (`assisted`, `helped`, `worked on`, `responsible for`, `handled`).
  - **Formatting Artifacts (-10 to -25 pts)**: Detects non-standard parser hazards such as HTML tables, images, multi-column tab structures, or progress bars.
  - **Brevity Violations (-5 to -15 pts)**: Penalizes resumes with word counts under 150 words or invalid bullet point lengths (< 5 or > 45 words).
  - **Quantified Metrics Gap (-10 to -15 pts)**: Penalizes resumes where less than 50% of bullet points contain measurable results (percentages `%`, currency `$`, multipliers `2x`, `100+`).
- **Actionable Feedback Payload**: Returns a 3-4 line dynamic recommendation breaking down exact skill gaps, verb replacements, and formatting fixes for scores < 75%.
- **Auto-Optimization Target**: Triggers HITL Gate 2/3 workflows to auto-tailor resume bullets to >85% ATS compatibility.

### 3. Resume Document Formatting Engine
- **Syntax Cleaning**: Strips markdown bolding (`**`) and em-dashes (`—` / `–`), replacing em-dashes with standard hyphens (`-`).
- **Typography & Uniformity**: Enforces uniform font sizes, heading weights, and spacing across all sections—specifically matching *Achievements & Extracurricular* headers to main experience entries.
- **DOCX Compilation**: Compiles clean, single-column Word documents strictly compliant with Workday, Lever, and Greenhouse parsers.

## Project Structure

- `config/constants.py`: Centralized weak verbs list, metric regex patterns (`METRIC_PATTERNS_REGEX`), formatting artifact rules, and penalty weights.
- `src/agents/ats_engine.py`: Penalty-based ATS scoring calibration engine with `_analyze_impact_verbs`, `_analyze_formatting_artifacts`, `_analyze_brevity`, and `_analyze_metric_density`.
- `src/utils/docx_compiler.py`: Document compiler with `clean_resume_syntax()` and uniform styling.
- `src/components/FeedbackCard.jsx`: Reusable React card for dynamic actionable feedback visualization (rendered when ATS score < 75%).
- `src/components/LandingPage.jsx`: Deep Purple pre-intake entry landing page with social proof cards and ATS Compliance Guide.

## Tests

Run:

```powershell
python -m pytest tests/
```