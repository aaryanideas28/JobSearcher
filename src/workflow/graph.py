# File: src/workflow/graph.py
"""LangGraph workflow assembly for resume automation."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Protocol

from src.workflow.state import AgentState

logger = logging.getLogger(__name__)

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


def process_intake(state: AgentState) -> AgentState:
    """Validate and normalize initial workflow state, routing based on intake_mode."""
    resume_text = (state.get("resume_text") or state.get("parsed_resume_text") or "").strip()
    structured = state.get("structured_intake") or {}

    if not resume_text and not structured:
        state["error"] = "MISSING_INTAKE_DATA"
        state["workflow_status"] = "failed"
        return state

    state.setdefault("feedback", [])
    state.setdefault("attempt_count", 0)
    state["workflow_status"] = "intake_complete"

    if state.get("intake_mode") == "build_from_scratch":
        from src.api.routes.intake import map_structured_intake_to_json, format_json_resume_to_text
        mapped_json = map_structured_intake_to_json(structured)
        state["user_resume_json"] = mapped_json
        
        contact = structured.get("contact_info") or {}
        state["target_role"] = state.get("target_role") or contact.get("target_role") or ""
        state["resume_text"] = format_json_resume_to_text(mapped_json)

    return state


async def emit_node_completion(
    state: AgentState,
    *,
    stage: str,
    workflow_status: str,
    message: str,
    pct: int,
) -> AgentState:
    """Persist and publish deterministic pipeline progress for the active session."""

    state["workflow_status"] = workflow_status
    metadata = state.setdefault("metadata", {})
    metadata["pipeline_stage"] = stage
    metadata["pipeline_message"] = message
    metadata["pipeline_pct"] = pct

    session_id = state.get("session_id")
    if not session_id:
        return state

    state_snapshot = dict(state)

    def persist_status() -> None:
        from src.database.connection import SessionLocal
        from src.database.models import WorkflowSession

        with SessionLocal() as db:
            session = db.get(WorkflowSession, session_id)
            if not session:
                return
            persisted_state = dict(session.state_json or {})
            persisted_state.update(state_snapshot)
            session.state_json = persisted_state
            session.status = workflow_status
            db.commit()

    await asyncio.to_thread(persist_status)

    from src.api.progress import progress_hub

    await progress_hub.publish(
        session_id,
        {
            "type": "pipeline_status",
            "session_id": session_id,
            "stage": stage,
            "workflow_status": workflow_status,
            "message": message,
            "pct": pct,
            "state": state_snapshot,
        },
    )
    return state


async def intake_node(state: AgentState) -> AgentState:
    """Run intake and emit completion status."""

    state = process_intake(state)
    if state.get("workflow_status") == "failed":
        return await emit_node_completion(
            state,
            stage="failed",
            workflow_status="failed",
            message="Intake failed.",
            pct=100,
        )
    return await emit_node_completion(
        state,
        stage="intake",
        workflow_status="intake_complete",
        message="Parsing...",
        pct=25,
    )


async def evaluate_initial_ats(state: AgentState) -> AgentState:
    """Audit the current resume without pausing for human approval."""
    if state.get("error") == "MISSING_INTAKE_DATA":
        return await emit_node_completion(
            state,
            stage="failed",
            workflow_status="failed",
            message="Audit skipped because intake failed.",
            pct=100,
        )

    state.setdefault("feedback", [])
    state.setdefault("attempt_count", 0)
    
    user_id = state.get("user_id") or 1
    import glob
    files = glob.glob(f"storage_workspace/uploads/user_{user_id}_original.*")
    if files:
        state["original_uploaded_file"] = str(Path(files[0]).resolve())
    else:
        state["original_uploaded_file"] = ""
        
    ats_score = state.get("ats_score")
    if ats_score is None:
        from src.agents.ats_engine import ATSEngine
        engine = ATSEngine()
        resume_text = state.get("resume_text") or ""
        job_desc = state.get("job_description") or ""
        score = await engine.combined_score(resume_text, job_desc)
        state["ats_score"] = score.details.get("ats_score", round(score.score * 100))
        state["ats_details"] = score.details
    elif isinstance(ats_score, (int, float)) and 0 <= ats_score <= 1:
        state["ats_score"] = round(float(ats_score) * 100)

    # Parse and check information density
    from src.utils.docx_compiler import DocxCompiler
    from src.schemas.resume import validate_resume_info_density
    
    resume_text = state.get("resume_text") or ""
    parsed_dict = DocxCompiler().parse_resume_text_to_dict(resume_text)
    has_sufficient_info, missing_fields = validate_resume_info_density(parsed_dict)

    state["needs_optimization_approval"] = False
    state["optimization_recommended"] = False
    state["information_density"] = {
        "has_sufficient_info": has_sufficient_info,
        "missing_fields": missing_fields,
    }

    return await emit_node_completion(
        state,
        stage="audit",
        workflow_status="audit_complete",
        message="Auditing...",
        pct=50,
    )


def initial_ats_routing(state: AgentState) -> str:
    """Backward-compatible routing hook; proactive pipeline always optimizes."""
    return "optimize"


def validate_input_node(state: AgentState) -> AgentState:
    """Backward-compatible validation node used by tests and older imports."""
    state["workflow_status"] = "validated"
    state["validation_errors"] = []
    return state


async def resume_optimizer_node(state: AgentState) -> AgentState:
    """Optimize the resume or generate from skills if no baseline exists."""
    if state.get("error") == "MISSING_INTAKE_DATA":
        return await emit_node_completion(
            state,
            stage="failed",
            workflow_status="failed",
            message="Optimization skipped because intake failed.",
            pct=100,
        )

    if (
        state.get("keep_original")
        or state.get("action") == "keep_original"
        or state.get("approve_optimization") is False
    ):
        state["optimized_resume"] = (
            state.get("resume_text") or state.get("uploaded_resume_text") or ""
        )
        original_resume_path = _original_resume_path(state)
        state["active_resume"] = original_resume_path
        if original_resume_path:
            state["original_uploaded_file"] = original_resume_path
            state["generated_document_path"] = original_resume_path
        state["workflow_status"] = "resume_optimized"
        return state

    from src.agents.optimizer import ResumeOptimizer
    optimizer = ResumeOptimizer()

    uploaded_resume_text = state.get("uploaded_resume_text") or ""
    resume_text = (state.get("resume_text") or uploaded_resume_text or "").strip()
    skills = state.get("skills_to_highlight") or []
    target_role = state.get("target_role") or ""

    if not resume_text and not skills:
        optimizer.raw_resume_text = uploaded_resume_text or state.get("resume_text") or ""
        state["optimized_resume"] = optimizer.raw_resume_text
        return await emit_node_completion(
            state,
            stage="optimize",
            workflow_status="resume_optimized",
            message="Optimization skipped because no candidate context was provided.",
            pct=75,
        )

    if state.get("intake_mode") == "build_from_scratch":
        from src.api.routes.intake import map_structured_intake_to_json, format_json_resume_to_text
        structured = state.get("structured_intake") or {}
        mapped_json = state.get("user_resume_json") or map_structured_intake_to_json(structured)
        state["user_resume_json"] = mapped_json
        raw_text_for_optimization = format_json_resume_to_text(mapped_json)
        job_desc = state.get("job_description", "")

        optimization = await optimizer.optimize_resume(
            resume_text=raw_text_for_optimization,
            job_description=job_desc,
            skills_to_highlight=skills,
            target_role=target_role,
        )
        state["optimized_resume"] = optimization.optimized_resume
        try:
            import json
            state["optimized_resume_json"] = json.loads(optimization.optimized_resume)
        except Exception:
            from src.utils.docx_compiler import DocxCompiler
            state["optimized_resume_json"] = DocxCompiler().parse_resume_text_to_dict(optimization.optimized_resume)
    else:
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
                from src.utils.docx_compiler import DocxCompiler
                parsed_resume = DocxCompiler().parse_resume_text_to_dict(optimization.optimized_resume)
                if not parsed_resume.get("contact", {}).get("name"):
                    orig_json = state.get("user_resume_json") or state.get("extracted_facts") or {}
                    orig_name = orig_json.get("contact", {}).get("name") or ""
                    parsed_resume["contact"]["name"] = orig_name
                state["optimized_resume_json"] = parsed_resume

    # 2. Compile PDF
    user_id = state.get("user_id") or 1
    attempt = state.get("attempt_count", 0) + 1
    state["attempt_count"] = attempt

    from src.utils.docx_compiler import DocxCompiler
    docx_compiler = DocxCompiler()
    docx_path = docx_compiler.compile_agent_state(state, "resume")
    state["generated_document_path"] = str(docx_path.resolve())
    return await emit_node_completion(
        state,
        stage="optimize",
        workflow_status="resume_optimized",
        message="Optimizing...",
        pct=75,
    )


async def ats_scoring_node(state: AgentState) -> AgentState:
    """ATS scoring of the optimized resume against the job description."""
    from src.agents.ats_engine import ATSEngine
    engine = ATSEngine()
    resume = state.get("optimized_resume") or state.get("resume_text") or ""
    job_desc = state.get("job_description") or ""
    score = await engine.combined_score(resume, job_desc)
    state["ats_score"] = score.details.get("ats_score", round(score.score * 100))
    state["ats_details"] = score.details
    state["workflow_status"] = "ats_scored"
    return state


def check_ats_threshold(state: AgentState) -> AgentState:
    """Backward-compatible threshold hook; never pauses the proactive pipeline."""
    state["optimization_recommended"] = False
    state["workflow_status"] = "audit_complete"
    return state


def human_optimization_pause(state: AgentState) -> AgentState:
    """Backward-compatible no-op for callers that still import the old gate node."""
    state["workflow_status"] = "audit_complete"
    return state


def check_ats_threshold_routing(state: AgentState) -> str:
    """Backward-compatible routing hook; proactive pipeline always proceeds."""
    return "proceed"


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
        max_results=6,
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


def _resume_text_for_outreach(state: AgentState) -> str:
    """Normalize raw or structured resume state for the outreach agent."""
    import json

    resume = state.get("optimized_resume")
    if resume is None or resume == "":
        resume = state.get("uploaded_resume_text") or state.get("resume_text") or ""

    if isinstance(resume, dict):
        return json.dumps(resume, indent=2, ensure_ascii=False)

    if isinstance(resume, str):
        stripped_resume = resume.strip()
        if stripped_resume:
            try:
                parsed_resume = json.loads(stripped_resume)
            except (TypeError, ValueError):
                return resume
            if isinstance(parsed_resume, dict):
                return json.dumps(parsed_resume, indent=2, ensure_ascii=False)
        return resume

    return str(resume)


def _original_resume_path(state: AgentState) -> str:
    """Resolve the original uploaded resume file for keep-original attachments."""
    candidates = [state.get("original_uploaded_file")]
    metadata = state.get("metadata") or {}
    if isinstance(metadata, dict):
        candidates.extend([metadata.get("original_file_path"), metadata.get("stored_path")])

    import glob
    user_id = state.get("user_id")
    if user_id:
        candidates.extend(glob.glob(f"storage_workspace/uploads/user_{user_id}_original.*"))

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return ""


def _candidate_name_for_outreach(state: AgentState, resume_text: str) -> str:
    """Resolve the candidate name from state, intake data, or resume text."""
    import json

    candidate_context = state.get("candidate_context") or {}
    if isinstance(candidate_context, dict):
        contact = candidate_context.get("contact") or candidate_context.get("contact_info") or {}
        if isinstance(contact, dict):
            name = contact.get("name") or contact.get("full_name")
            if name:
                return str(name).strip()
        name = candidate_context.get("name") or candidate_context.get("full_name")
        if name:
            return str(name).strip()
    elif isinstance(candidate_context, str) and candidate_context.strip():
        for line in candidate_context.splitlines():
            if line.lower().strip().startswith("name:"):
                name = line.split(":", 1)[1].strip()
                if name:
                    return name

    for source in (
        state.get("candidate_name"),
        (state.get("user_resume_json") or {}).get("contact", {}).get("name")
        if isinstance(state.get("user_resume_json"), dict)
        else None,
        (state.get("structured_intake") or {}).get("full_name")
        if isinstance(state.get("structured_intake"), dict)
        else None,
        (state.get("structured_intake") or {}).get("contact_info", {}).get("full_name")
        if isinstance((state.get("structured_intake") or {}).get("contact_info"), dict)
        else None,
    ):
        if source:
            return str(source).strip()

    try:
        parsed_resume = json.loads(resume_text)
        if isinstance(parsed_resume, dict):
            contact = parsed_resume.get("contact") or parsed_resume.get("contact_info") or {}
            if isinstance(contact, dict) and contact.get("name"):
                return str(contact["name"]).strip()
            if parsed_resume.get("name"):
                return str(parsed_resume["name"]).strip()
    except (TypeError, ValueError):
        pass

    for line in resume_text.splitlines():
        candidate_line = line.strip()
        if candidate_line.lower().startswith("name:"):
            name = candidate_line.split(":", 1)[1].strip()
            if name:
                return name

    for candidate_line in resume_text.splitlines()[:8]:
        candidate_line = candidate_line.strip()
        if (
            candidate_line
            and len(candidate_line) <= 80
            and "@" not in candidate_line
            and not candidate_line.startswith(("{", "}", "[", "]", '"'))
            and not any(
                header in candidate_line.lower()
                for header in ("resume", "curriculum vitae", "summary", "experience", "skills")
            )
        ):
            return candidate_line
    return ""


def _company_name_from_job_description(job_description: str) -> str:
    """Extract an explicit company label from common job-description formats."""
    import re

    patterns = (
        r"(?im)^\s*(?:company|employer|organization)\s*[:\-]\s*([^\n,]+)",
        r"(?i)\b(?:at|join)\s+([A-Z][A-Za-z0-9&'.-]*(?:\s+[A-Z][A-Za-z0-9&'.-]*){0,3})",
    )
    for pattern in patterns:
        match = re.search(pattern, job_description or "")
        if match:
            return match.group(1).strip(" .,:;|\t")
    return ""


async def outreach_node(state: AgentState) -> AgentState:
    """Draft email outreach for the selected job."""
    from src.agents.outreach import OutreachAgent, extract_contact_email, infer_recruiter_email
    agent = OutreachAgent()

    selected_job = state.get("selected_job") or (state.get("discovered_jobs")[0] if state.get("discovered_jobs") else {})
    state["selected_job"] = selected_job

    job_desc = (
        selected_job.get("description")
        or selected_job.get("job_description")
        or state.get("job_description")
        or ""
    )
    company_name = (
        _company_name_from_job_description(job_desc)
        or selected_job.get("company")
        or selected_job.get("company_name")
        or state.get("target_company")
        or ""
    )
    role_title = (
        selected_job.get("title")
        or selected_job.get("role_title")
        or state.get("target_role")
        or ""
    )
    resume_text = _resume_text_for_outreach(state)
    candidate_name = state.get("candidate_name") or _candidate_name_for_outreach(state, resume_text)
    candidate_skills = state.get("core_skills") or state.get("skills_to_highlight") or []
    job_metadata = selected_job.get("metadata") or selected_job.get("metadata_json") or {}
    recipient_email = (
        selected_job.get("recruiter_email")
        or selected_job.get("contact_email")
        or (job_metadata.get("recruiter_email") if isinstance(job_metadata, dict) else None)
        or extract_contact_email(job_desc)
        or state.get("recipient_email")
        or infer_recruiter_email(company_name)
    )
    attachment_path = state.get("generated_document_path") or _original_resume_path(state)

    cover_letter = await agent.draft_cover_letter(
        resume_text=resume_text,
        job_description=job_desc,
        company_name=company_name,
        candidate_name=candidate_name,
        target_role=role_title,
        candidate_skills=candidate_skills,
    )
    state["cover_letter"] = cover_letter

    email_payload = agent.build_email_payload(
        recipient_email=recipient_email,
        subject=f"Application for {role_title} at {company_name}",
        body=cover_letter,
        attachments=[attachment_path] if attachment_path else [],
        metadata={
            "session_id": state.get("session_id"),
            "user_id": state.get("user_id"),
            "job_title": role_title,
            "company_name": company_name,
        }
    )
    from dataclasses import asdict
    state["email_payload"] = asdict(email_payload)
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
    try:
        from src.workflow.tasks import send_email_outreach_task
        email_payload = state.get("email_payload") or {}
        attachments = email_payload.get("attachments") or []
        valid_attachments = [str(Path(path).resolve()) for path in attachments if Path(str(path)).is_file()]
        if not valid_attachments:
            generated_path = state.get("generated_document_path") or _original_resume_path(state)
            if generated_path and Path(generated_path).is_file():
                valid_attachments = [str(Path(generated_path).resolve())]
        email_payload["attachments"] = valid_attachments
        state["email_payload"] = email_payload

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
    except Exception as exc:
        logger.exception(
            "Outreach dispatch failed: session_id=%s state_keys=%s "
            "has_email_payload=%s",
            state.get("session_id"),
            sorted(state.keys()),
            bool(state.get("email_payload")),
        )
        state["error"] = f"Outreach dispatch failed: {type(exc).__name__}: {exc}"
        state["workflow_status"] = "failed"
        raise


def dispatch_node(state: AgentState) -> AgentState:
    """Document delivery / output stage node."""
    if state.get("approve_optimization") == False:
        user_id = state.get("user_id") or 1
        import glob
        files = glob.glob(f"storage_workspace/uploads/user_{user_id}_original.*")
        if files:
            state["generated_document_path"] = str(Path(files[0]).resolve())
            
            # Update attachments in email payload if present
            if "email_payload" in state and state["email_payload"]:
                email_payload = state["email_payload"]
                if hasattr(email_payload, "attachments"):
                    email_payload.attachments = [state["generated_document_path"]]
                elif isinstance(email_payload, dict):
                    email_payload["attachments"] = [state["generated_document_path"]]
            if "email_draft" in state and state["email_draft"]:
                if isinstance(state["email_draft"], dict):
                    state["email_draft"]["attachments"] = [state["generated_document_path"]]

    return dispatch_outreach_node(state)


async def complete_node(state: AgentState) -> AgentState:
    """Finalize the proactive ATS pipeline."""
    try:
        if state.get("error") == "MISSING_INTAKE_DATA":
            return await emit_node_completion(
                state,
                stage="failed",
                workflow_status="failed",
                message="Pipeline failed.",
                pct=100,
            )

        resume = state.get("optimized_resume") or state.get("resume_text") or ""
        job_desc = state.get("job_description") or ""
        if resume and job_desc:
            from src.agents.ats_engine import ATSEngine

            score = await ATSEngine().combined_score(resume, job_desc)
            state["ats_score"] = score.details.get("ats_score", round(score.score * 100))
            state["matching_score"] = state["ats_score"]
            state["ats_details"] = score.details

        state["active_resume"] = state.get("generated_document_path") or state.get("original_uploaded_file") or ""
        return await emit_node_completion(
            state,
            stage="complete",
            workflow_status="completed",
            message="Complete",
            pct=100,
        )
    except Exception as exc:
        logger.exception(
            "Workflow completion failed: session_id=%s state_keys=%s",
            state.get("session_id"),
            sorted(state.keys()),
        )
        state["error"] = f"Workflow completion failed: {type(exc).__name__}: {exc}"
        state["workflow_status"] = "failed"
        raise


def build_workflow_graph() -> Any:
    """Assemble and compile the workflow graph."""
    graph = StateGraph(AgentState)
    graph.add_node("intake", intake_node)
    graph.add_node("evaluate_initial_ats", evaluate_initial_ats)
    graph.add_node("resume_optimizer", resume_optimizer_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("complete", complete_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "evaluate_initial_ats")
    graph.add_edge("evaluate_initial_ats", "resume_optimizer")
    graph.add_edge("resume_optimizer", "outreach")
    graph.add_edge("outreach", "complete")
    graph.add_edge("complete", END)

    if _HAS_LANGGRAPH:
        return graph.compile(checkpointer=MemorySaver())
    return graph.compile()


workflow_graph = build_workflow_graph()
graph = workflow_graph
