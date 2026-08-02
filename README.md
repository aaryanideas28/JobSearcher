# Startum Job Agent

Startum is an AI-assisted job application platform built with FastAPI and LangGraph. It helps candidates upload or build resumes, discover jobs, tailor resumes, calculate ATS scores, draft recruiter outreach, review results, and approve dispatch through human-in-the-loop (HITL) gates.

## Features

- PDF resume upload and text extraction.
- Guided build-from-scratch intake for candidate details, skills, education, experience, projects, certifications, and achievements.
- Structured extraction of candidate name, email, phone, and core skills.
- Job discovery and manually selected job targets.
- LangGraph workflow orchestration with resumable HITL checkpoints.
- Keep-original and AI-optimization paths with safe empty-context fallbacks.
- Truth-preserving resume optimization that must not invent employers, dates, skills, achievements, or metrics.
- Deterministic ATS scoring for skill coverage, required/preferred skills, role-keyword density, structure, formatting, impact verbs, brevity, and measurable impact.
- ATS explanation with overview, radar categories, highlights, and actionable improvements.
- ATS recalculation after editing a generated resume.
- DOCX generation with Minimal ATS, Modern Tech, Classic Executive, and Compact One-Page templates.
- Job-specific outreach email drafting.
- Resume attachment resolution for outreach emails.
- SMTP or Gmail API delivery, with optional Celery/Redis background processing.
- FastAPI Swagger documentation and browser dashboard.

## Architecture

    Browser dashboard or API client
                    |
                    v
              FastAPI routes
                    |
       +------------+-------------+
       |            |             |
    Resume       LangGraph      ATS
    parsing      workflow       engine
       |            |             |
       +------------+-------------+
                    |
             DOCX and outreach
                    |
          SQLite/PostgreSQL + Redis

Important directories:

- src/api: FastAPI application and route handlers.
- src/workflow: LangGraph state, graph nodes, and Celery tasks.
- src/agents: optimizer, outreach, ATS, and safety agents.
- src/utils/docx_compiler.py: structured resume to DOCX rendering.
- storage_workspace/templates: dashboard and document templates.
- database: database connection and schema support.
- tests: automated tests.

## Requirements

- Python 3.11 or newer.
- Docker Desktop if using PostgreSQL and Redis.
- Optional Ollama installation for local LLM generation.
- Optional Tavily or another configured job-search provider.
- Optional SMTP credentials or Gmail OAuth credentials for email delivery.

## Installation

Run commands from the repository root.

### Windows PowerShell

    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

If PowerShell blocks activation:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\.venv\Scripts\Activate.ps1

### macOS/Linux

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

## Environment Configuration

Create a .env file in the project root. Never commit real credentials.

    APP_NAME=Startum Job Agent
    APP_ENV=development
    APP_DEBUG=true
    API_V1_PREFIX=/api/v1

    # SQLite is the simplest local option.
    DATABASE_URL=sqlite:///./resume_automation.db

    REDIS_URL=redis://localhost:6379/0
    CELERY_BROKER_URL=redis://localhost:6379/1
    CELERY_RESULT_BACKEND=redis://localhost:6379/2
    TAVILY_API_KEY=

    # Optional integrations.
    OPENAI_API_KEY=
    HF_API_KEY=

    # SMTP or Gmail OAuth.
    EMAIL_SENDER=no-reply@example.com
    SMTP_HOST=
    SMTP_PORT=587
    SMTP_USERNAME=
    SMTP_PASSWORD=
    GMAIL_CLIENT_ID=
    GMAIL_CLIENT_SECRET=
    GMAIL_REFRESH_TOKEN=

    # Synchronous local email execution.
    CELERY_TASK_ALWAYS_EAGER=true

    # Replace this outside development.
    AUTH_TOKEN_SECRET=change-me-in-production

## Optional Ollama Setup

Start Ollama separately and pull the configured model:

    ollama serve
    ollama pull llama3

The API can start without Ollama, but AI generation may use fallback behavior or require another configured provider.

## Start PostgreSQL and Redis

SQLite is the default and requires no Docker services. To use the included services:

    docker compose up -d

Stop them with:

    docker compose down

For PostgreSQL, set DATABASE_URL to:

    postgresql+psycopg2://resume_user:resume_password@localhost:5432/resume_automation

Initialize local tables when needed:

    python -c "from database.connection import init_db; init_db()"

## Start the Application

    uvicorn src.api.main:app --reload

Open these URLs:

- Dashboard: http://127.0.0.1:8000/dashboard/
- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health: http://127.0.0.1:8000/health

For production-like local execution, omit --reload and configure a production database, secret, CORS origins, and email provider.

## Optional Celery Worker

By default, CELERY_TASK_ALWAYS_EAGER=true and email tasks run in the API process. For background delivery:

1. Set CELERY_TASK_ALWAYS_EAGER=false.
2. Start Redis.
3. Start the worker in another terminal:

    celery -A src.workflow.tasks.celery_app worker --loglevel=info --pool=solo

A queued response requires the worker to remain running.

## Dashboard Workflow

1. Open the dashboard.
2. Enter candidate contact details, target role, skills, locations, and work mode.
3. Choose a resume template.
4. Upload a PDF or choose Build from Scratch.
5. Review discovered jobs and select a target role.
6. Review the ATS score, radar explanation, highlights, and improvements.
7. Choose Auto-Optimize Resume, Keep Original, or the scratch-build option at the HITL gate.
8. Review the resume and outreach draft.
9. Edit the resume and use Recalculate ATS & Refresh Advice if needed.
10. Approve the final resume and email.
11. Verify the recipient, subject, body, and attachment before dispatch.

The selected template controls the generated DOCX layout. The editable resume text is content-focused; template differences are visible in the generated/downloaded DOCX.


### Outreach

- POST /outreach/generate-email: generate a personalized draft.
- POST /outreach/dispatch: send or queue the email and resolve its attachment.

Possible dispatch statuses include sent, queued, failed, and skipped_no_email_config. Queued means a task was submitted; it does not guarantee provider delivery.

## ATS Scoring

The ATS engine is deterministic by default. It evaluates:

- Canonical skill overlap and aliases.
- Required versus preferred skill coverage.
- Role-specific keyword density.
- Standard resume headings and contact completeness.
- Weak or low-impact phrasing.
- Brevity and measurable achievement signals.
- Formatting and parser risks.

The radar is diagnostic. A category at 100 means no weakness was detected for that category. Job-to-job variation usually comes from skills and content alignment. Suggestions must remain grounded in the candidate's actual resume and must not invent metrics.

## Email and Attachment Troubleshooting

If email dispatch does not send:

1. Configure either SMTP or all required Gmail OAuth variables.
2. If using Celery, confirm Redis and the Celery worker are running.
3. Inspect the dispatch response fields status, result, task_id, and attachment.
4. Confirm the attachment path exists under storage_workspace.
5. Check provider authentication, TLS/SSL settings, spam folders, and provider restrictions.

The dispatch route resolves attachments from the request, workflow session, generated documents, or uploaded-file metadata.

## Testing

Run the complete test suite:

    python -m pytest tests/ -q

Run focused tests:

    python -m pytest tests/test_ats_engine.py -q
    python -m pytest tests/test_optimizer.py -q

Check the working tree:

    git diff --check

Compile source files:

    python -m compileall -q src config database

## Troubleshooting

### ModuleNotFoundError

Activate the virtual environment and reinstall:

    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

### Database connection failure

Start with SQLite:

    DATABASE_URL=sqlite:///./resume_automation.db

Use PostgreSQL only after docker compose up -d reports healthy services.

### Port already in use

    uvicorn src.api.main:app --reload --port 8001

### Python or Uvicorn points to the wrong interpreter

Verify the active executables:

    Get-Command python
    Get-Command uvicorn
    python --version

Then activate .venv again and reinstall dependencies.




