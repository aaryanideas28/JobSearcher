# File: src/api/routes/jobs.py
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models import JobTarget, User
from src.agents.job_discovery import JobDiscoveryAgent
from src.api.dependencies import get_db

router = APIRouter()


class ManualJobTargetRequest(BaseModel):
    """Manual job target selected by the user."""

    user_id: int = Field(..., ge=1)
    company_name: str = Field(..., min_length=1)
    role_title: str = Field(..., min_length=1)
    job_description: str = Field(..., min_length=1)
    job_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobDiscoveryRequest(BaseModel):
    """Job discovery query for Tavily-backed search."""

    user_id: int = Field(..., ge=1)
    query: str = Field(..., min_length=3)
    max_results: int = Field(default=5, ge=1, le=20)
    persist: bool = True
    source: str = "tavily"
    preferred_locations: list[str] = Field(default_factory=list)
    work_mode: str | None = "Any"


@router.post("/manual")
async def create_manual_job_target(
    payload: ManualJobTargetRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Create a manually selected job target for optimization."""

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    job_target = JobTarget(
        user_id=payload.user_id,
        company_name=payload.company_name,
        role_title=payload.role_title,
        job_url=payload.job_url,
        job_description=payload.job_description,
        status="selected",
        preferred_locations=[],
        work_mode="Any",
        metadata_json={"source": "manual_selection", **payload.metadata},
    )
    db.add(job_target)
    db.commit()
    db.refresh(job_target)
    return {
        "status": "stored",
        "job_target_id": job_target.id,
        "user_id": job_target.user_id,
        "company_name": job_target.company_name,
        "role_title": job_target.role_title,
        "hitl_gate": {
            "gate": "gate-2",
            "message": "Review this job target and approve the optimization scope.",
            "approval_endpoint": "/api/v1/hitl/gate-2",
        },
    }


@router.post("/discover")
async def discover_jobs(
    payload: JobDiscoveryRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Discover job postings through Tavily and optionally persist them."""

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    pref_locations = payload.preferred_locations
    w_mode = payload.work_mode

    if not pref_locations or w_mode == "Any" or w_mode is None:
        from src.database.models import CandidatePreference
        preference = (
            db.query(CandidatePreference)
            .filter(CandidatePreference.user_id == payload.user_id)
            .order_by(CandidatePreference.created_at.desc(), CandidatePreference.id.desc())
            .first()
        )
        if preference:
            if not pref_locations:
                pref_locations = preference.preferred_locations
            if w_mode == "Any" or w_mode is None:
                w_mode = getattr(preference, "work_mode", "Any")

    postings = await JobDiscoveryAgent().discover(
        query=payload.query,
        max_results=payload.max_results,
        source=payload.source,
        preferred_locations=pref_locations,
        work_mode=w_mode,
    )
    stored: list[dict[str, Any]] = []
    if payload.persist:
        for posting in postings:
            job_target = JobTarget(
                user_id=payload.user_id,
                company_name=posting.company,
                role_title=posting.title,
                job_url=posting.url,
                job_description=posting.description or posting.title,
                status="discovered",
                preferred_locations=pref_locations or [],
                work_mode=w_mode or "Any",
                metadata_json=posting.metadata,
            )
            db.add(job_target)
            db.flush()
            stored.append(
                {
                    "job_target_id": job_target.id,
                    "company_name": job_target.company_name,
                    "role_title": job_target.role_title,
                    "job_url": job_target.job_url,
                }
            )
        db.commit()

    return {
        "status": "discovered" if postings else "no_results_or_tavily_not_configured",
        "query": payload.query,
        "count": len(postings),
        "stored": stored,
        "results": [
            {
                "title": posting.title,
                "company": posting.company,
                "url": posting.url,
                "description_preview": posting.description[:500],
                "metadata": posting.metadata,
            }
            for posting in postings
        ],
    }
