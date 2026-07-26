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

Run the API:

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

## Key API Routes

- `POST /api/v1/auth/login`: create or load a user and return a bearer token.
- `GET /api/v1/auth/me`: inspect the current bearer-token user.
- `GET /api/v1/intake/questions`: list the questions the app should ask before optimization.
- `POST /api/v1/intake/profile`: store target role, skills to highlight, locations, and preferences.
- `POST /api/v1/resume/upload`: store a resume text version.
- `POST /api/v1/resume/upload-file`: upload a TXT, MD, PDF, or DOCX resume and parse it into a resume version.
- `POST /api/v1/resume/rollback`: mark a prior resume version as selected.
- `POST /api/v1/jobs/manual`: manually create the target job to optimize against.
- `POST /api/v1/workflow/manual-optimize-draft`: route to Ollama, optimize the resume, score ATS fit, and generate an email draft.
- `POST /api/v1/hitl/gate-1`: approve resume selection.
- `POST /api/v1/hitl/gate-2`: approve job target and optimization scope.
- `POST /api/v1/hitl/gate-3`: approve final outreach dispatch.
- `POST /api/v1/outreach/dispatch`: queue an email outreach payload.

## Manual Vertical Slice

Use this flow to test the first real product path:

1. `POST /api/v1/auth/login`
2. `GET /api/v1/intake/questions`
3. `POST /api/v1/intake/profile`
4. `POST /api/v1/resume/upload-file` or `POST /api/v1/resume/upload`
5. `POST /api/v1/hitl/gate-1`
6. `POST /api/v1/jobs/manual`
7. `POST /api/v1/hitl/gate-2`
8. `POST /api/v1/workflow/manual-optimize-draft`
9. Review the returned `email_draft` and `hitl_gate.approval_payload`
10. `POST /api/v1/hitl/gate-3`
11. `POST /api/v1/outreach/dispatch`

Ollama is used automatically through `OLLAMA_BASE_URL`, `OLLAMA_SMALL_MODEL`, and `OLLAMA_LARGE_MODEL`. If Ollama is not running, the optimizer and outreach agent return deterministic fallback drafts so the workflow remains testable.

## Tests

Run:

```powershell
pytest
```

If Windows resolves `python` to the Store alias, use your virtual environment explicitly:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Notes

This is an executable scaffold. It includes type-safe boundaries, persistence hooks, queue hooks, security checks, and rendering templates, but the production integrations are intentionally thin. The next implementation steps are Gmail OAuth send support, real Tavily search, Ollama/vLLM client calls, workflow persistence/checkpointing, and websocket progress events.
