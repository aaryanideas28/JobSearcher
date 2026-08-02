"""Services that prepare and invoke the matching workflow."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from src.database.models import Candidate, Job, WorkflowSession
from src.database.connection import SessionLocal
from src.workflow import AgentState, graph
from src.api.progress import progress_hub


def _build_initial_state(candidate: Candidate, job: Job, session_id: str) -> AgentState:
    latest_resume = candidate.resumes[0] if candidate.resumes else None
    resume_text = ""
    if latest_resume is not None:
        resume_text = latest_resume.parsed_text or latest_resume.content

    requirements = ", ".join(job.requirements)
    job_description = job.description
    if requirements:
        job_description = f"{job_description}\n\nRequirements: {requirements}"

    initial_state = AgentState(
        session_id=session_id,
        user_id=candidate.id,
        job_id=job.id,
        job_description=job_description,
        resume_text=resume_text,
        target_role=job.title,
        target_company=job.company,
        workflow_status="started",
    )
    return initial_state


async def create_match_session(candidate: Candidate, job: Job) -> str:
    """Create the durable session record before the background pipeline starts."""

    session_id = str(uuid4())
    latest_resume = candidate.resumes[0] if candidate.resumes else None
    initial_state = _build_initial_state(candidate, job, session_id)
    initial_state["metadata"] = {
        "pipeline_stage": "accepted",
        "pipeline_message": "Accepted",
        "pipeline_pct": 0,
    }

    with SessionLocal() as db:
        session = WorkflowSession(
            id=session_id,
            user_id=candidate.id,
            resume_version_id=latest_resume.id if latest_resume else None,
            job_target_id=None,
            status="accepted",
            state_json=dict(initial_state),
        )
        db.add(session)
        db.commit()

    await progress_hub.publish(
        session_id,
        {
            "type": "pipeline_status",
            "session_id": session_id,
            "stage": "accepted",
            "workflow_status": "accepted",
            "message": "Accepted",
            "pct": 0,
            "state": dict(initial_state),
        },
    )
    return session_id


async def _load_match_entities(candidate_id: int, job_id: int) -> tuple[Candidate | None, Job | None]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    def load() -> tuple[Candidate | None, Job | None]:
        with SessionLocal() as db:
            candidate = db.scalar(
                select(Candidate)
                .where(Candidate.id == candidate_id)
                .options(selectinload(Candidate.resumes))
            )
            job = db.scalar(select(Job).where(Job.id == job_id))
            return candidate, job

    return await asyncio.to_thread(load)


async def run_match_pipeline(session_id: str, candidate_id: int, job_id: int) -> dict[str, Any]:
    """Execute the pipeline for an already accepted match session."""

    candidate, job = await _load_match_entities(candidate_id, job_id)
    if candidate is None or job is None:
        failed_state: dict[str, Any] = {
            "session_id": session_id,
            "workflow_status": "failed",
            "error": "MATCH_INPUT_NOT_FOUND",
            "metadata": {
                "pipeline_stage": "failed",
                "pipeline_message": "Candidate or job could not be loaded.",
                "pipeline_pct": 100,
            },
        }
        with SessionLocal() as db:
            session = db.get(WorkflowSession, session_id)
            if session:
                session.status = "failed"
                session.state_json = failed_state
                db.commit()
        await progress_hub.publish(session_id, {"type": "pipeline_status", **failed_state})
        return failed_state

    initial_state = _build_initial_state(candidate, job, session_id)

    with SessionLocal() as db:
        session = db.get(WorkflowSession, session_id)
        if session:
            session.status = "running"
            session.state_json = dict(initial_state)
            db.commit()

    config = {"configurable": {"thread_id": session_id}}
    try:
        result = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        failed_state = dict(initial_state)
        failed_state["workflow_status"] = "failed"
        failed_state["error"] = str(exc)
        failed_state["metadata"] = {
            "pipeline_stage": "failed",
            "pipeline_message": str(exc) or "Pipeline failed.",
            "pipeline_pct": 100,
        }
        with SessionLocal() as db:
            session = db.get(WorkflowSession, session_id)
            if session:
                session.state_json = failed_state
                session.status = "failed"
                db.commit()
        await progress_hub.publish(
            session_id,
            {
                "type": "pipeline_status",
                "session_id": session_id,
                "stage": "failed",
                "workflow_status": "failed",
                "message": "Pipeline failed.",
                "pct": 100,
                "state": failed_state,
            },
        )
        return failed_state

    resumed_dict = dict(result)
    with SessionLocal() as db:
        session = db.get(WorkflowSession, session_id)
        if session:
            session.state_json = resumed_dict
            session.status = resumed_dict.get("workflow_status") or "running"
            db.commit()

    await progress_hub.publish(
        session_id,
        {
            "type": "pipeline_status",
            "session_id": session_id,
            "stage": "complete",
            "workflow_status": resumed_dict.get("workflow_status"),
            "message": "Complete",
            "pct": 100,
            "state": resumed_dict,
        },
    )
    return resumed_dict


async def process_match(candidate: Candidate, job: Job) -> dict[str, Any]:
    """Backward-compatible synchronous-style helper for callers that await completion."""

    session_id = await create_match_session(candidate, job)
    return await run_match_pipeline(session_id, candidate.id, job.id)


async def get_match_status(session_id: str) -> dict[str, Any] | None:
    """Return polling status and final result for a match session."""

    def normalize_stage(stage: str) -> str:
        return {
            "accepted": "Queued",
            "intake": "Parsing",
            "intake_complete": "Parsing",
            "audit": "Auditing",
            "audit_complete": "Auditing",
            "optimize": "Optimizing",
            "resume_optimized": "Optimizing",
            "complete": "Complete",
            "completed": "Complete",
            "failed": "Failed",
        }.get(stage, stage.title() if stage else "Queued")

    def feedback_points(details: dict[str, Any]) -> list[str]:
        actionable_feedback = str(details.get("actionable_feedback") or "")
        points = []
        for line in actionable_feedback.splitlines():
            clean_line = line.strip().lstrip("-* ").removeprefix("\u2022").strip()
            if clean_line:
                points.append(clean_line)
        return points[:5]

    def document_url(path_value: str | None) -> str | None:
        if not path_value:
            return None
        normalized = path_value.replace("\\", "/")
        marker = "storage_workspace/"
        if marker in normalized:
            return f"/static/{normalized.split(marker, 1)[1]}"
        return normalized

    def load_status() -> dict[str, Any] | None:
        with SessionLocal() as db:
            session = db.get(WorkflowSession, session_id)
            if not session:
                return None
            state = dict(session.state_json or {})
            metadata = state.get("metadata") or {}
            stage = metadata.get("pipeline_stage") or session.status
            message = metadata.get("pipeline_message") or state.get("error") or session.status
            pct = metadata.get("pipeline_pct") or (100 if session.status in {"completed", "failed"} else 0)
            ats_details = state.get("ats_details") or {}
            score = state.get("matching_score") or state.get("ats_score")
            doc_url = document_url(state.get("generated_document_path"))
            result = None
            if session.status == "completed":
                result = {
                    "candidate_id": state.get("user_id"),
                    "matching_score": score,
                    "final_ats_score": score,
                    "workflow_status": state.get("workflow_status"),
                    "ats_details": ats_details,
                    "top_feedback_points": feedback_points(ats_details),
                    "optimized_resume": state.get("optimized_resume"),
                    "generated_document_path": state.get("generated_document_path"),
                    "doc_url": doc_url,
                }
            return {
                "job_id": state.get("job_id"),
                "session_id": session_id,
                "status": session.status,
                "workflow_status": session.status,
                "stage": stage,
                "message": message,
                "pct": pct,
                "execution_stage": normalize_stage(stage),
                "execution_pct": pct,
                "execution_message": message,
                "final_payload": result,
                "result": result,
            }

    return await asyncio.to_thread(load_status)


__all__ = ["create_match_session", "get_match_status", "process_match", "run_match_pipeline"]
