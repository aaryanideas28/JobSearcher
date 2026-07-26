# File: src/api/routes/jobs.py
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import JobTarget, User
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

    postings = await JobDiscoveryAgent().discover(query=payload.query, max_results=payload.max_results)
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
