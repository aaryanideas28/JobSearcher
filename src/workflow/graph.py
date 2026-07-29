# File: src/workflow/graph.py
"""LangGraph workflow assembly for resume automation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from src.workflow.state import AgentState

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.checkpoint.memory import MemorySaver
    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover
    START = "__start__"
    END = "__end__"
    _HAS_LANGGRAPH = False

    class StateGraph:  # type: ignore[no-redef]
        """Tiny fallback graph builder used when langgraph is not installed."""

        def __init__(self, state_type: type[AgentState]) -> None:
            self.state_type = state_type
            self.nodes: dict[str, Any] = {}
            self.edges: list[tuple[str, str]] = []

        def add_node(self, name: str, node: Any) -> None:
            self.nodes[name] = node

        def add_edge(self, source: str, target: str) -> None:
            self.edges.append((source, target))

        def compile(self) -> "StateGraph":
            return self

    class MemorySaver:  # type: ignore[no-redef]
        pass


class CompiledGraph(Protocol):
    """Protocol for compiled graph objects."""

    def invoke(self, input: AgentState) -> AgentState:
        """Invoke the graph."""
        ...


def intake_node(state: AgentState) -> AgentState:
    """Validate and normalize initial workflow state."""
    state["workflow_status"] = "intake_complete"
    state.setdefault("feedback", [])
    state.setdefault("attempt_count", 0)
    return state


def validate_input_node(state: AgentState) -> AgentState:
    """Backward-compatible validation node used by tests and older imports."""
    state["workflow_status"] = "validated"
    state["validation_errors"] = []
    return state


async def resume_optimizer_node(state: AgentState) -> AgentState:
    """Optimize the resume or generate from skills if no baseline exists."""
    from src.agents.optimizer import ResumeOptimizer
    optimizer = ResumeOptimizer()

    resume_text = state.get("resume_text", "").strip()
    skills = state.get("skills_to_highlight") or []
    target_role = state.get("target_role") or "Software Engineer"

    # 1. Synthesize if no baseline
    if not resume_text:
        resume_json = await optimizer.build_resume_from_skills(skills, target_role)
        state["user_resume_json"] = resume_json
        state["optimized_resume_json"] = resume_json
        import json
        state["optimized_resume"] = json.dumps(resume_json, indent=2)
        state["resume_text"] = state["optimized_resume"]
    else:
        # Optimize existing resume text
        job_desc = state.get("job_description", "")
        optimization = await optimizer.optimize_resume(
            resume_text=resume_text,
            job_description=job_desc,
            skills_to_highlight=skills,
            target_role=target_role
        )
        state["optimized_resume"] = optimization.optimized_resume
        try:
            import json
            state["optimized_resume_json"] = json.loads(optimization.optimized_resume)
        except Exception:
            state["optimized_resume_json"] = {
                "contact": {"name": "Candidate"},
                "summary": "Optimized Resume",
                "skills": skills,
                "experience": [{"company": state.get("target_company") or "Target Company", "role": target_role, "description": optimization.optimized_resume}]
            }

    # 2. Compile PDF
    user_id = state.get("user_id") or 1
    attempt = state.get("attempt_count", 0) + 1
    state["attempt_count"] = attempt

    from src.utils.docx_compiler import DocxCompiler
    docx_compiler = DocxCompiler()
    docx_path = docx_compiler.compile_agent_state(state, "resume")
    state["generated_document_path"] = str(docx_path.resolve())
    state["workflow_status"] = "resume_optimized"
    return state


async def ats_scoring_node(state: AgentState) -> AgentState:
    """ATS scoring of the optimized resume against the job description."""
    from src.agents.ats_engine import ATSEngine
    engine = ATSEngine()
    resume = state.get("optimized_resume") or state.get("resume_text") or ""
    job_desc = state.get("job_description") or ""
    score = await engine.combined_score(resume, job_desc)
    state["ats_score"] = score.score
    state["ats_details"] = score.details
    state["workflow_status"] = "ats_scored"
    return state


async def job_discovery_node(state: AgentState) -> AgentState:
    """Discover jobs using Tavily."""
    from src.agents.job_discovery import JobDiscoveryAgent
    target_role = state.get("target_role") or "Software Engineer"
    skills = state.get("skills_to_highlight") or []
    preferred_locations = state.get("preferred_locations") or []
    work_mode = state.get("work_mode") or "Any"
    query = f"{target_role} jobs " + " ".join(skills[:3])

    agent = JobDiscoveryAgent()
    postings = await agent.discover(
        query=query,
        max_results=10,
        preferred_locations=preferred_locations,
        work_mode=work_mode,
    )

    discovered = []
    for posting in postings:
        desc = posting.description
        extracted_skills = []
        for skill in skills:
            if skill.lower() in desc.lower():
                extracted_skills.append(skill)
        if not extracted_skills:
            common_skills = ["Python", "FastAPI", "Go", "Java", "SQL", "Docker", "Kubernetes", "AWS", "React", "TypeScript"]
            for s in common_skills:
                if s.lower() in desc.lower():
                    extracted_skills.append(s)

        discovered.append({
            "title": posting.title,
            "company": posting.company,
            "url": posting.url,
            "description": desc,
            "extracted_skills": extracted_skills,
            "metadata": posting.metadata
        })

    state["discovered_jobs"] = discovered
    state["workflow_status"] = "jobs_discovered"
    return state


async def outreach_node(state: AgentState) -> AgentState:
    """Draft email outreach for the selected job."""
    from src.agents.outreach import OutreachAgent
    agent = OutreachAgent()

    selected_job = state.get("selected_job") or (state.get("discovered_jobs")[0] if state.get("discovered_jobs") else {})
    state["selected_job"] = selected_job

    job_desc = selected_job.get("description") or state.get("job_description") or ""
    company_name = selected_job.get("company") or state.get("target_company") or "Target Company"
    role_title = selected_job.get("title") or state.get("target_role") or "Software Engineer"
    resume_text = state.get("optimized_resume") or state.get("resume_text") or ""

    cover_letter = await agent.draft_cover_letter(
        resume_text=resume_text,
        job_description=job_desc,
        company_name=company_name,
    )
    state["cover_letter"] = cover_letter

    email_payload = agent.build_email_payload(
        recipient_email=state.get("recipient_email") or "review-before-send@example.com",
        subject=f"Application for {role_title} at {company_name}",
        body=cover_letter,
        attachments=[state.get("generated_document_path")] if state.get("generated_document_path") else [],
        metadata={
            "session_id": state.get("session_id"),
            "user_id": state.get("user_id"),
            "job_title": role_title,
            "company_name": company_name,
        }
    )
    state["email_payload"] = email_payload
    state["workflow_status"] = "outreach_drafted"
    return state


def validation_node(state: AgentState) -> AgentState:
    """Validate outreach draft and run security checks."""
    from src.security.validation import HallucinationDetector
    detector = HallucinationDetector()
    validation = detector.detect_cover_letter(state)
    state["quality_checks"] = {
        "hallucination_valid": validation.valid,
        "hallucination_reasons": validation.reasons
    }
    state["workflow_status"] = "awaiting_human_review"
    return state


def dispatch_outreach_node(state: AgentState) -> AgentState:
    """Dispatches the outreach email via Celery."""
    from src.workflow.tasks import send_email_outreach_task
    email_payload = state.get("email_payload") or {}

    from src.config.settings import get_settings
    settings = get_settings()

    if settings.celery_task_always_eager:
        result = send_email_outreach_task(email_payload)
    else:
        delay = getattr(send_email_outreach_task, "delay", None)
        if callable(delay):
            async_result = delay(email_payload)
            result = {"status": "queued", "task_id": getattr(async_result, "id", None)}
        else:
            result = send_email_outreach_task(email_payload)

    state["workflow_status"] = "completed"
    state.setdefault("metadata", {})
    state["metadata"]["dispatch_result"] = result
    return state


def build_workflow_graph() -> Any:
    """Assemble and compile the workflow graph."""
    graph = StateGraph(AgentState)
    graph.add_node("intake", intake_node)
    graph.add_node("resume_optimizer", resume_optimizer_node)
    graph.add_node("ats_scoring", ats_scoring_node)
    graph.add_node("job_discovery", job_discovery_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("validation", validation_node)
    graph.add_node("dispatch_outreach", dispatch_outreach_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "resume_optimizer")
    graph.add_edge("resume_optimizer", "ats_scoring")
    graph.add_edge("resume_optimizer", "job_discovery")
    graph.add_edge("ats_scoring", "outreach")
    graph.add_edge("job_discovery", "outreach")
    graph.add_edge("outreach", "validation")
    graph.add_edge("validation", "dispatch_outreach")
    graph.add_edge("dispatch_outreach", END)

    if _HAS_LANGGRAPH:
        return graph.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["resume_optimizer", "outreach", "dispatch_outreach"]
        )
    return graph.compile()


workflow_graph = build_workflow_graph()
graph = workflow_graph
