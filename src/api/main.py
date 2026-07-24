# File: src/api/main.py
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from src.api.routes import hitl, outreach, resume

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router, prefix=f"{settings.api_v1_prefix}/resume", tags=["resume"])
app.include_router(hitl.router, prefix=f"{settings.api_v1_prefix}/hitl", tags=["human-in-the-loop"])
app.include_router(outreach.router, prefix=f"{settings.api_v1_prefix}/outreach", tags=["outreach"])


@app.get("/health")
async def health() -> dict[str, Any]:
    """Return service health metadata."""

    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}
