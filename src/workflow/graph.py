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


def process_intake(state: AgentState) -> AgentState:
    """Validate and normalize initial workflow state, routing based on intake_mode."""
    state.setdefault("intake_mode", "upload")
    state.setdefault("feedback", [])
    state.setdefault("attempt_count", 0)
    state["workflow_status"] = "intake_complete"

    if state.get("intake_mode") == "build_from_scratch":
        from src.api.routes.intake import map_structured_intake_to_json, format_json_resume_to_text
        structured = state.get("structured_intake") or {}
        mapped_json = map_structured_intake_to_json(structured)
        state["user_resume_json"] = mapped_json
        
        contact = structured.get("contact_info") or {}
        state["target_role"] = state.get("target_role") or contact.get("target_role") or ""
        state["resume_text"] = format_json_resume_to_text(mapped_json)

    return state


async def evaluate_initial_ats(state: AgentState) -> AgentState:
    """Evaluate initial ATS score of uploaded resume and handle interrupt if below threshold."""
    state.setdefault("intake_mode", "upload")
    state.setdefault("feedback", [])
    state.setdefault("attempt_count", 0)
    
    user_id = state.get("user_id") or 1
    import glob
    files = glob.glob(f"storage_workspace/uploads/user_{user_id}_original.*")
    if files:
        state["original_uploaded_file"] = str(Path(files[0]).resolve())
    else:
        state["original_uploaded_file"] = ""
        
    if state.get("intake_mode") == "build_from_scratch":
        return state
        
    ats_score = state.get("ats_score")
    if ats_score is None:
        from src.agents.ats_engine import ATSEngine
        engine = ATSEngine()
        resume_text = state.get("resume_text") or ""
        job_desc = state.get("job_description") or ""
        score = await engine.combined_score(resume_text, job_desc)
        ats_score = score.score
        if ats_score <= 1.0:
            ats_score = ats_score * 100.0
        state["ats_score"] = ats_score
        state["ats_details"] = score.details

    # Parse and check information density
    from src.utils.docx_compiler import DocxCompiler
    from src.schemas.resume import validate_resume_info_density
    
    resume_text = state.get("resume_text") or ""
    parsed_dict = DocxCompiler().parse_resume_text_to_dict(resume_text)
    has_sufficient_info, missing_fields = validate_resume_info_density(parsed_dict)
    
    if state.get("approve_optimization") == False:
        state["active_resume"] = state.get("original_uploaded_file", "")
        return state

    if state.get("intake_mode") == "upload" and ats_score < 80 and state.get("approve_optimization") is None:
        from langgraph.types import interrupt
        if not has_sufficient_info:
            state["recommendation"] = "switch_to_scratch_build"
            state["needs_optimization_approval"] = True
            state["workflow_status"] = "interrupted"
            decision = interrupt({
                "type": "insufficient_data_warning",
                "missing_fields": missing_fields,
                "ats_score": ats_score,
                "message": "The uploaded resume has an ATS score below 80% and has insufficient information. To avoid generating default or fake information, please choose the option to build your resume from scratch."
            })
        else:
            state["recommendation"] = "prompt_optimization"
            state["needs_optimization_approval"] = True
            state["workflow_status"] = "interrupted"
            decision = interrupt({
                "type": "low_ats_optimization_prompt",
                "ats_score": ats_score
            })
            
        state["needs_optimization_approval"] = False
        state["workflow_status"] = "ats_scored"
        
        if decision is True or decision == "optimize":
            if not has_sufficient_info and ats_score < 80:
                raise ValueError(
                    "Cannot optimize resume with ATS score < 80% and insufficient information. "
                    "Please use the build from scratch option to avoid generating default or fake information."
                )
            state["approve_optimization"] = True
        elif decision is False or decision == "keep_original":
            state["approve_optimization"] = False
            state["active_resume"] = state.get("original_uploaded_file", "")
        elif decision == "switch_to_scratch":
            state["intake_mode"] = "build_from_scratch"
            state["approve_optimization"] = True
            # Re-generate resume baseline from empty/structured form
            from src.api.routes.intake import map_structured_intake_to_json, format_json_resume_to_text
            structured = state.get("structured_intake") or {}
            mapped_json = map_structured_intake_to_json(structured)
            state["user_resume_json"] = mapped_json
            state["resume_text"] = format_json_resume_to_text(mapped_json)
            
    return state


def initial_ats_routing(state: AgentState) -> str:
    """Route conditionally after initial ATS evaluation."""
    if state.get("intake_mode") == "build_from_scratch":
        return "optimize"
    if state.get("approve_optimization") == False:
        return "dispatch"
    return "optimize"


def validate_input_node(state: AgentState) -> AgentState:
    """Backward-compatible validation node used by tests and older imports."""
    state["workflow_status"] = "validated"
    state["validation_errors"] = []
    return state


async def resume_optimizer_node(state: AgentState) -> AgentState:
    """Optimize the resume or generate from skills if no baseline exists."""
    if state.get("approve_optimization") == False:
        state["optimized_resume"] = state.get("resume_text", "")
        state["active_resume"] = state.get("original_uploaded_file") or ""
        if state.get("original_uploaded_file"):
            state["generated_document_path"] = state["original_uploaded_file"]
        state["workflow_status"] = "resume_optimized"
        return state

    from src.agents.optimizer import ResumeOptimizer
    optimizer = ResumeOptimizer()

    resume_text = state.get("resume_text", "").strip()
    skills = state.get("skills_to_highlight") or []
    target_role = state.get("target_role") or "Software Engineer"

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
                if not parsed_resume.get("contact", {}).get("name") or parsed_resume["contact"]["name"] == "Candidate":
                    orig_json = state.get("user_resume_json") or state.get("extracted_facts") or {}
                    orig_name = orig_json.get("contact", {}).get("name") or "Candidate"
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


def check_ats_threshold(state: AgentState) -> AgentState:
    """Check ATS score and set status/optimization recommendation."""
    if state.get("approve_optimization") == False:
        state["optimization_recommended"] = False
        state["workflow_status"] = "ats_scored"
        return state

    if state.get("intake_mode") == "build_from_scratch":
        state["optimization_recommended"] = False
        state["workflow_status"] = "ats_scored"
        return state

    ats_score = state.get("ats_score", 0.0)
    # Convert float score to percentage representation if it's 0-1
    if ats_score <= 1.0:
        ats_score_percent = ats_score * 100.0
    else:
        ats_score_percent = ats_score

    state["ats_score"] = ats_score

    if ats_score_percent < 80:
        state["optimization_recommended"] = True
        state["workflow_status"] = "PAUSED_FOR_HUMAN_OPTIMIZATION_APPROVAL"
    else:
        state["optimization_recommended"] = False
    return state


def human_optimization_pause(state: AgentState) -> AgentState:
    """Gate node where execution halts for human decision."""
    state["workflow_status"] = "PAUSED_FOR_HUMAN_OPTIMIZATION_APPROVAL"
    return state


def check_ats_threshold_routing(state: AgentState) -> str:
    """Route conditionally based on ATS score threshold."""
    if state.get("approve_optimization") == False:
        return "dispatch"

    if state.get("intake_mode") == "build_from_scratch":
        return "proceed"

    ats_score = state.get("ats_score", 0.0)
    if ats_score <= 1.0:
        ats_score_percent = ats_score * 100.0
    else:
        ats_score_percent = ats_score

    if ats_score_percent < 80:
        return "paused"
    else:
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


def build_workflow_graph() -> Any:
    """Assemble and compile the workflow graph."""
    graph = StateGraph(AgentState)
    graph.add_node("intake", process_intake)
    graph.add_node("evaluate_initial_ats", evaluate_initial_ats)
    graph.add_node("resume_optimizer", resume_optimizer_node)
    graph.add_node("ats_scoring", ats_scoring_node)
    graph.add_node("check_ats_threshold", check_ats_threshold)
    graph.add_node("human_optimization_pause", human_optimization_pause)
    graph.add_node("job_discovery", job_discovery_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("validation", validation_node)
    graph.add_node("dispatch_outreach", dispatch_outreach_node)
    graph.add_node("dispatch_node", dispatch_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "evaluate_initial_ats")
    
    # Conditional edge after initial ATS check
    graph.add_conditional_edges(
        "evaluate_initial_ats",
        initial_ats_routing,
        {
            "optimize": "resume_optimizer",
            "dispatch": "dispatch_node"
        }
    )
    
    graph.add_edge("resume_optimizer", "ats_scoring")
    graph.add_edge("resume_optimizer", "job_discovery")
    
    # Conditional edge after ats_scoring (via check_ats_threshold)
    graph.add_edge("ats_scoring", "check_ats_threshold")
    graph.add_conditional_edges(
        "check_ats_threshold",
        check_ats_threshold_routing,
        {
            "paused": "human_optimization_pause",
            "proceed": "outreach",
            "dispatch": "dispatch_node"
        }
    )
    graph.add_edge("human_optimization_pause", "outreach")

    graph.add_edge("job_discovery", "outreach")
    graph.add_edge("outreach", "validation")
    graph.add_edge("validation", "dispatch_node")
    graph.add_edge("dispatch_outreach", "dispatch_node")
    graph.add_edge("dispatch_node", END)

    if _HAS_LANGGRAPH:
        return graph.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["human_optimization_pause", "outreach", "dispatch_outreach"]
        )
    return graph.compile()


workflow_graph = build_workflow_graph()
graph = workflow_graph
