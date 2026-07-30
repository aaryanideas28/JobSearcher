# File: src/api/routes/templates.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class TemplatePreset(BaseModel):
    id: str
    name: str
    description: str
    preview_url: str

@router.get("", response_model=list[TemplatePreset])
async def get_templates() -> list[TemplatePreset]:
    """Return a list of available resume template presets and their metadata."""
    return [
        TemplatePreset(
            id="minimal_ats",
            name="Minimal ATS",
            description="High-density single-column centered layout for technical roles.",
            preview_url="/static/templates/previews/minimal_ats.png",
        ),
        TemplatePreset(
            id="modern_tech",
            name="Modern Tech",
            description="Clean sans-serif left-aligned layout with modern teal accents.",
            preview_url="/static/templates/previews/modern_tech.png",
        ),
        TemplatePreset(
            id="classic_executive",
            name="Classic Executive",
            description="Elegant serif centered layout with deep navy highlights.",
            preview_url="/static/templates/previews/classic_executive.png",
        ),
        TemplatePreset(
            id="compact_onepage",
            name="Compact One-Page",
            description="Ultra-condensed layout with narrow margins for single page fitment.",
            preview_url="/static/templates/previews/compact_onepage.png",
        ),
    ]
