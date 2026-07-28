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

## Tests

Run:

```powershell
pytest
```

If Windows resolves `python` to the Store alias, use your virtual environment explicitly:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
.venv\Scripts\activate