# File: src/api/main.py
"""FastAPI application entrypoint for the AI Resume Automation Platform."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from src.api.routes import auth, dashboard, hitl, intake, jobs, outreach, resume, workflow

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered resume optimization, job targeting, HITL approval, and outreach automation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["resume"])
app.include_router(intake.router, prefix="/api/v1/intake", tags=["intake"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(workflow.router, prefix="/api/v1/workflow", tags=["workflow"])
app.include_router(hitl.router, prefix="/api/v1/hitl", tags=["human-in-the-loop"])
app.include_router(outreach.router, prefix="/api/v1/outreach", tags=["outreach"])
from fastapi.staticfiles import StaticFiles

app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.mount("/static", StaticFiles(directory="storage_workspace"), name="static")


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Return a friendly pointer to the dashboard and API docs."""
    return {
        "message": "AI Resume Automation Platform is running.",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Basic service health check."""
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}
