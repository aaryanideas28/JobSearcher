# File: src/api/routes/dashboard.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
TEMPLATE_PATH = Path("storage_workspace/templates/dashboard.html")


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Serve the lightweight local dashboard."""

    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))
