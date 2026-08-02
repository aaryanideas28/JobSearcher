"""FastAPI entry point for candidate-to-job matching."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.connection import SessionLocal, init_db
from database.models import Candidate, Job, Resume
from src.api.routes import auth, dashboard, hitl, intake, jobs, outreach, resume, workflow
from src.services.processor import create_match_session, get_match_status, run_match_pipeline
from src.utils.resume_parser import ResumeParser

init_db()

from fastapi.responses import RedirectResponse

app = FastAPI(title="AI Resume Automation Platform")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["resume"])
app.include_router(intake.router, prefix="/api/v1/intake", tags=["intake"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(workflow.router, prefix="/api/v1/workflow", tags=["workflow"])
app.include_router(hitl.router, prefix="/api/v1/hitl", tags=["human-in-the-loop"])
app.include_router(outreach.router, prefix="/api/v1/outreach", tags=["outreach"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.mount("/static", StaticFiles(directory="storage_workspace"), name="static")


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root access directly to the landing page and dashboard."""
    return RedirectResponse(url="/dashboard/")




class MatchRequest(BaseModel):
    """Identifiers for a candidate-to-job matching request."""

    job_id: int = Field(..., ge=1)
    candidate_id: int = Field(..., ge=1)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return the application health status."""

    return {"status": "ok"}


@app.post("/pipeline/start")
@app.post("/match")
async def match_candidate(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Accept matching inputs and start the candidate-to-job workflow asynchronously."""

    content_type = request.headers.get("content-type", "")

    async def parse_match_request() -> tuple[int, int]:
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            raw_job_id = form.get("job_id")
            raw_candidate_id = form.get("candidate_id")
            uploaded_file = form.get("file")
            if raw_job_id is None:
                raise HTTPException(status_code=422, detail="job_id is required")
            if raw_candidate_id is not None:
                return int(raw_candidate_id), int(str(raw_job_id))
            if not hasattr(uploaded_file, "filename") or not uploaded_file.filename:
                raise HTTPException(status_code=422, detail="file is required when candidate_id is omitted")

            email = str(form.get("email") or "").strip()
            full_name = str(form.get("full_name") or "Uploaded Candidate").strip()
            if not email:
                email = f"candidate-{uuid4().hex[:12]}@local.invalid"

            upload_dir = Path("storage_workspace/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(uploaded_file.filename).suffix.lower() or ".txt"
            stored_path = upload_dir / f"match_{uuid4().hex}{suffix}"
            stored_path.write_bytes(await uploaded_file.read())
            parsed = ResumeParser().parse(stored_path)
            if not parsed.text:
                raise HTTPException(status_code=422, detail="Could not extract resume text")

            def persist_uploaded_candidate() -> int:
                with SessionLocal() as db:
                    candidate = db.query(Candidate).filter(Candidate.email == email).one_or_none()
                    if candidate is None:
                        candidate = Candidate(name=full_name, email=email, skills=[], current_role=None)
                        db.add(candidate)
                        db.flush()
                    db.add(Resume(candidate_id=candidate.id, content=parsed.text, parsed_text=parsed.text))
                    db.commit()
                    return candidate.id

            return await asyncio.to_thread(persist_uploaded_candidate), int(str(raw_job_id))

        payload = MatchRequest(**(await request.json()))
        return payload.candidate_id, payload.job_id

    candidate_id, job_id = await parse_match_request()

    def load_match_inputs() -> tuple[Candidate | None, Job | None]:
        with SessionLocal() as db:
            candidate = db.scalar(
                select(Candidate)
                .where(Candidate.id == candidate_id)
                .options(selectinload(Candidate.resumes))
            )
            job = db.scalar(select(Job).where(Job.id == job_id))
            return candidate, job

    candidate, job = await asyncio.to_thread(load_match_inputs)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    session_id = await create_match_session(candidate, job)
    background_tasks.add_task(run_match_pipeline, session_id, candidate.id, job.id)
    return {
        "session_id": session_id,
        "candidate_id": candidate.id,
        "job_id": job.id,
        "workflow_status": "accepted",
        "status_url": f"/match/{session_id}/status",
        "pipeline_status_url": f"/pipeline/{session_id}/status",
    }


@app.get("/pipeline/{session_id}/status")
@app.get("/match/{session_id}/status")
async def match_status(session_id: str) -> dict[str, Any]:
    """Return the latest persisted pipeline progress for a match job."""

    status_payload = await get_match_status(session_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail="Match job not found")
    return status_payload
