"""FastAPI entry point for candidate-to-job matching."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.connection import SessionLocal
from database.models import Candidate, Job
from src.services.processor import process_match

app = FastAPI(title="AI Resume Automation Platform")


class MatchRequest(BaseModel):
    """Identifiers for a candidate-to-job matching request."""

    job_id: int = Field(..., ge=1)
    candidate_id: int = Field(..., ge=1)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return the application health status."""

    return {"status": "ok"}


@app.post("/match")
async def match_candidate(
    payload: MatchRequest,
) -> dict[str, Any]:
    """Load matching inputs and trigger the candidate-to-job workflow."""

    def load_match_inputs() -> tuple[Candidate | None, Job | None]:
        with SessionLocal() as db:
            candidate = db.scalar(
                select(Candidate)
                .where(Candidate.id == payload.candidate_id)
                .options(selectinload(Candidate.resumes))
            )
            job = db.scalar(select(Job).where(Job.id == payload.job_id))
            return candidate, job

    candidate, job = await asyncio.to_thread(load_match_inputs)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await process_match(candidate, job)
    return {
        "candidate_id": candidate.id,
        "job_id": job.id,
        "matching_score": result.get("matching_score"),
        "workflow_status": result.get("workflow_status"),
    }
