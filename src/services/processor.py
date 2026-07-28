"""Services that prepare and invoke the matching workflow."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.database.models import Candidate, Job, WorkflowSession
from src.database.connection import SessionLocal
from src.workflow import AgentState, graph
from src.api.progress import progress_hub


async def process_match(candidate: Candidate, job: Job) -> dict[str, Any]:
    """Prepare candidate and job data, then execute the matching graph with checkpointer and DB state."""

    latest_resume = candidate.resumes[0] if candidate.resumes else None
    resume_text = ""
    if latest_resume is not None:
        resume_text = latest_resume.parsed_text or latest_resume.content

    requirements = ", ".join(job.requirements)
    job_description = job.description
    if requirements:
        job_description = f"{job_description}\n\nRequirements: {requirements}"

    session_id = str(uuid4())
    initial_state = AgentState(
        session_id=session_id,
        user_id=candidate.id,
        job_description=job_description,
        resume_text=resume_text,
        target_role=job.title,
        target_company=job.company,
        workflow_status="started",
    )

    # 1. Create WorkflowSession in database
    with SessionLocal() as db:
        session = WorkflowSession(
            id=session_id,
            user_id=candidate.id,
            resume_version_id=latest_resume.id if latest_resume else None,
            job_target_id=None,
            status="started",
            state_json=dict(initial_state),
        )
        db.add(session)
        db.commit()

    # 2. Invoke graph using checkpointer configurable thread_id
    config = {"configurable": {"thread_id": session_id}}
    result = await graph.ainvoke(initial_state, config=config)

    # 3. Update session state in database
    resumed_dict = dict(result)
    with SessionLocal() as db:
        session = db.get(WorkflowSession, session_id)
        if session:
            session.state_json = resumed_dict
            session.status = resumed_dict.get("workflow_status") or "running"
            db.commit()

    if session_id:
        await progress_hub.publish(
            session_id,
            {"type": "workflow_state", "workflow_status": resumed_dict.get("workflow_status"), "state": resumed_dict},
        )
    return resumed_dict


__all__ = ["process_match"]
