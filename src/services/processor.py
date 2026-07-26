"""Services that prepare and invoke the matching workflow."""

from __future__ import annotations

from typing import Any

from database.models import Candidate, Job
from src.workflow import AgentState, graph
from src.api.progress import progress_hub


async def process_match(candidate: Candidate, job: Job) -> dict[str, Any]:
    """Prepare candidate and job data, then execute the matching graph."""

    latest_resume = candidate.resumes[0] if candidate.resumes else None
    resume_text = ""
    if latest_resume is not None:
        resume_text = latest_resume.parsed_text or latest_resume.content

    requirements = ", ".join(job.requirements)
    job_description = job.description
    if requirements:
        job_description = f"{job_description}\n\nRequirements: {requirements}"

    initial_state = AgentState(
        job_description=job_description,
        resume_text=resume_text,
    )
    result = await graph.ainvoke(initial_state.model_dump())
    if isinstance(result, AgentState):
        if result.session_id:
            await progress_hub.publish(
                result.session_id,
                {"type": "workflow_state", "workflow_status": result.workflow_status, "state": result.model_dump(mode="json")},
            )
        return result.model_dump()
    return dict(result)


__all__ = ["process_match"]
