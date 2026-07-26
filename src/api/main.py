# File: src/api/main.py
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config.settings import get_settings
from src.api.routes import hitl, outreach, resume
from src.api.progress import progress_hub
from src.workflow.tasks import celery_app

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
    """Return readiness based on independent, short connectivity checks."""

    checks = await asyncio.gather(_check_postgres(), _check_redis(), _check_ollama())
    dependencies = {name: result for name, result in checks}
    ready = all(result["available"] for result in dependencies.values())
    return {
        "status": "ready" if ready else "degraded",
        "service": settings.app_name,
        "environment": settings.app_env,
        "dependencies": dependencies,
    }


@app.websocket("/ws/progress/{session_id}")
async def workflow_progress(websocket: WebSocket, session_id: str) -> None:
    """Push in-process LangGraph state events to a connected UI client."""

    await progress_hub.connect(session_id, websocket)
    try:
        while True:
            # Receiving occasional client heartbeats avoids an active polling loop.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await progress_hub.disconnect(session_id, websocket)


@app.websocket("/ws/tasks/{task_id}")
async def celery_progress(websocket: WebSocket, task_id: str) -> None:
    """Report Celery task state without executing worker work in the API process."""

    await websocket.accept()
    last_state: str | None = None
    try:
        while True:
            result = await asyncio.to_thread(celery_app.AsyncResult, task_id)
            if result.state != last_state:
                await websocket.send_json({"type": "celery_task", "task_id": task_id, "state": result.state})
                last_state = result.state
            if result.ready():
                return
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


async def _check_postgres() -> tuple[str, dict[str, Any]]:
    def check() -> None:
        from database.connection import engine
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    return "postgres", await _availability(check)


async def _check_redis() -> tuple[str, dict[str, Any]]:
    def check() -> None:
        from redis import Redis
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            client.ping()
        finally:
            client.close()

    return "redis", await _availability(check)


async def _check_ollama() -> tuple[str, dict[str, Any]]:
    try:
        timeout = httpx.Timeout(2.0, connect=1.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return "ollama", {"available": False, "error": type(exc).__name__}
    return "ollama", {"available": True}


async def _availability(check: Any) -> dict[str, Any]:
    try:
        await asyncio.to_thread(check)
    except Exception as exc:
        return {"available": False, "error": type(exc).__name__}
    return {"available": True}

    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}
