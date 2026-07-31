# File: src/api/routes/hitl.py
"""Human-in-the-loop approval gates."""

from __future__ import annotations

from typing import Any

from pathlib import Path
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models import HitlDecision, ResumeVersion, WorkflowSession, JobTarget, GeneratedDocument, CandidatePreference
from src.api.dependencies import get_db
from src.agents.optimizer import ResumeOptimizer
from src.agents.ats_engine import ATSEngine
from src.agents.outreach import OutreachAgent
from src.utils.docx_compiler import DocxCompiler


class ResumeOptimizationDecision(BaseModel):
    """Payload for low ATS score resume optimization decision."""

    user_id: int
    job_id: str
    action: str = Field(..., description="Action to take: 'optimize' or 'proceed_as_is'")

router = APIRouter()


class GateDecision(BaseModel):
    """Request payload for HITL approval gates."""

    session_id: str | None = None
    approved: bool = Field(default=False)
    reviewer_email: str | None = None
    notes: str | None = None
    edited_resume: str | None = None
    edited_email_subject: str | None = None
    edited_email_body: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _record_gate_decision(gate_name: str, payload: GateDecision, db: Session) -> dict[str, Any]:
    """Persist gate decision, apply edits, and resume the workflow graph."""
    if not payload.approved and not payload.notes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection requires notes so the agent can revise.",
        )

    session: WorkflowSession | None = None
    if payload.session_id:
        session = db.get(WorkflowSession, payload.session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow session not found.",
        )

    state = dict(session.state_json or {})
    edits_applied: list[str] = []

    if payload.edited_resume:
        state["optimized_resume"] = payload.edited_resume
        if session.resume_version_id is not None:
            resume_version = db.get(ResumeVersion, session.resume_version_id)
            if resume_version is not None:
                resume_version.optimized_text = payload.edited_resume
        edits_applied.append("optimized_resume")

    if payload.edited_email_subject or payload.edited_email_body:
        email_draft = dict(state.get("email_draft") or state.get("email_payload") or {})
        if payload.edited_email_subject:
            email_draft["subject"] = payload.edited_email_subject
            edits_applied.append("email_subject")
        if payload.edited_email_body:
            email_draft["body"] = payload.edited_email_body
            edits_applied.append("email_body")
        state["email_draft"] = email_draft
        state["email_payload"] = email_draft

    state[f"{gate_name}_approved"] = payload.approved
    state[f"{gate_name}_notes"] = payload.notes
    session.state_json = state

    db.add(
        HitlDecision(
            session_id=session.id,
            gate_name=gate_name,
            approved=payload.approved,
            reviewer_email=payload.reviewer_email,
            notes=payload.notes,
            edits_json={
                "edited_resume": payload.edited_resume,
                "edited_email_subject": payload.edited_email_subject,
                "edited_email_body": payload.edited_email_body,
                "metadata": payload.metadata,
            },
        )
    )
    db.commit()

    if payload.approved:
        from src.workflow.graph import graph
        config = {"configurable": {"thread_id": session.id}}

        values: dict[str, Any] = {
            f"hitl_{gate_name.replace('-', '_')}_approved": True,
        }
        if payload.edited_resume:
            values["resume_text"] = payload.edited_resume
            values["optimized_resume"] = payload.edited_resume
        if payload.edited_email_body or payload.edited_email_subject:
            values["email_payload"] = state.get("email_payload") or {}

        if gate_name == "gate-2":
            selected_job = None
            if payload.metadata and "selected_job" in payload.metadata:
                selected_job = payload.metadata["selected_job"]
            elif payload.metadata and "job_target_id" in payload.metadata:
                job_target = db.get(JobTarget, payload.metadata["job_target_id"])
                if job_target:
                    selected_job = {
                        "title": job_target.role_title,
                        "company": job_target.company_name,
                        "url": job_target.job_url,
                        "description": job_target.job_description,
                    }
            if selected_job:
                values["selected_job"] = selected_job

        node_map = {
            "gate-1": "resume_optimizer",
            "gate-2": "outreach",
            "gate-3": "dispatch_outreach",
        }
        target_node = node_map.get(gate_name, gate_name)

        # Update the graph state
        await graph.aupdate_state(config, values, as_node=target_node)

        # Resume the graph
        resumed_state = await graph.ainvoke(None, config=config)

        if isinstance(resumed_state, dict):
            session.state_json = dict(resumed_state)
            session.status = resumed_state.get("workflow_status") or "running"
            db.commit()
    else:
        session.status = f"{gate_name}_rejected"
        db.commit()

    return {
        "status": "approved" if payload.approved else "rejected",
        "gate": gate_name,
        "session_id": payload.session_id,
        "persisted": True,
        "edits_applied": edits_applied,
        "next_action": "continue_workflow" if payload.approved else "revise_draft",
    }


@router.post("/gate-1")
async def approve_gate_1(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject resume selection."""
    return await _record_gate_decision("gate-1", payload, db)


@router.post("/gate-2")
async def approve_gate_2(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject selected job target."""
    return await _record_gate_decision("gate-2", payload, db)


@router.post("/gate-3")
async def approve_gate_3(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject final optimized resume and email draft."""
    return await _record_gate_decision("gate-3", payload, db)


@router.post("/resume-optimization-decision")
async def resume_optimization_decision(
    payload: ResumeOptimizationDecision,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Handle HITL decision for resume optimization when ATS score is low."""
    try:
        job_target_id = int(payload.job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job_id format. Must be numeric.",
        )

    session = (
        db.query(WorkflowSession)
        .filter(
            WorkflowSession.user_id == payload.user_id,
            WorkflowSession.job_target_id == job_target_id
        )
        .order_by(WorkflowSession.created_at.desc())
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow session not found.",
        )

    resume_version = db.get(ResumeVersion, session.resume_version_id)
    job_target = db.get(JobTarget, session.job_target_id)
    if not resume_version or not job_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume version or job target not found.",
        )

    preference = (
        db.query(CandidatePreference)
        .filter(CandidatePreference.user_id == payload.user_id)
        .order_by(CandidatePreference.created_at.desc(), CandidatePreference.id.desc())
        .first()
    )
    selected_skills = (
        session.state_json.get("skills_to_highlight") 
        if session.state_json and "skills_to_highlight" in session.state_json 
        else (preference.skills_to_highlight if preference else [])
    )
    target_role = preference.target_role if preference else job_target.role_title

    ats_score_val = None
    optimized_resume_val = None
    email_draft_val = None
    generated_document_path = None

    if payload.action == "optimize":
        from src.schemas.resume import validate_resume_info_density
        from src.utils.docx_compiler import DocxCompiler
        parsed_dict = DocxCompiler().parse_resume_text_to_dict(resume_version.raw_text)
        has_sufficient_info, missing_fields = validate_resume_info_density(parsed_dict)
        
        uploaded_ats_score = resume_version.ats_score or 0.0
        if uploaded_ats_score <= 1.0:
            uploaded_ats_score *= 100.0
            
        if uploaded_ats_score < 80 and not has_sufficient_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded resume has an ATS score below 80% and has insufficient information. "
                       "Optimization is not allowed to prevent generating fake/default information. "
                       "Please use the 'switch_to_scratch' option to build your resume from scratch.",
            )

        optimizer = ResumeOptimizer()
        optimization = await optimizer.optimize_resume(
            resume_text=resume_version.raw_text,
            job_description=job_target.job_description,
            skills_to_highlight=selected_skills,
            target_role=target_role,
        )

        ats_engine = ATSEngine()
        ats_score = await ats_engine.combined_score(optimization.optimized_resume, job_target.job_description)

        optimized_resume_json = None
        try:
            import json
            optimized_resume_json = json.loads(optimization.optimized_resume)
        except Exception:
            optimized_resume_json = DocxCompiler().parse_resume_text_to_dict(optimization.optimized_resume)
            if not optimized_resume_json.get("contact", {}).get("name") or optimized_resume_json["contact"]["name"] == "Candidate":
                optimized_resume_json["contact"]["name"] = resume_version.user.full_name
            if not optimized_resume_json.get("contact", {}).get("email"):
                optimized_resume_json["contact"]["email"] = resume_version.user.email

        pdf_dir = Path("storage_workspace/final_documents") / f"user_{resume_version.user_id}"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        docx_path = pdf_dir / f"resume_v{resume_version.id}.docx"

        docx_compiler = DocxCompiler()
        docx_path = docx_compiler.compile_docx_state({
            "optimized_resume_json": optimized_resume_json,
            "user_resume_json": optimized_resume_json,
            "target_role": target_role,
            "target_company": job_target.company_name,
            "user_id": resume_version.user_id,
            "attempt_count": resume_version.id,
            "template_id": getattr(resume_version, "template_id", "minimal_ats")
        }, docx_path)

        attached_path = docx_path.resolve()
        generated_document_path = str(attached_path)

        generated_document = GeneratedDocument(
            user_id=resume_version.user_id,
            resume_version_id=resume_version.id,
            document_type="optimized_resume_docx",
            file_path=generated_document_path,
            metadata_json={"job_target_id": job_target.id, "source": "hitl_optimization"},
        )
        db.add(generated_document)

        resume_version.optimized_text = optimization.optimized_resume
        resume_version.ats_score = ats_score.score
        db.add(resume_version)

        outreach_agent = OutreachAgent()
        cover_letter = await outreach_agent.draft_cover_letter(
            resume_text=optimization.optimized_resume,
            job_description=job_target.job_description,
            company_name=job_target.company_name,
        )
        email_payload = outreach_agent.build_email_payload(
            recipient_email=session.state_json.get("email_draft", {}).get("recipient_email") or "review-before-send@example.com",
            subject=f"Application for {job_target.role_title} at {job_target.company_name}",
            body=cover_letter,
            attachments=[generated_document_path],
            metadata={
                "resume_version_id": resume_version.id,
                "job_target_id": job_target.id,
                "candidate_preference_id": preference.id if preference else None,
                "skills_to_highlight": selected_skills,
                "requires_hitl_gate": "gate-3",
            },
        )
        email_draft_val = asdict(email_payload)
        ats_score_val = ats_score.score
        optimized_resume_val = optimization.optimized_resume

        session.status = "draft_ready_for_human_review"
        state = dict(session.state_json or {})
        state["optimized_resume"] = optimized_resume_val
        state["ats_score"] = ats_score_val
        state["generated_document_path"] = generated_document_path
        state["optimization_recommended"] = False
        state["email_draft"] = email_draft_val
        state["email_payload"] = email_draft_val
        session.state_json = state
        db.commit()

        try:
            from src.workflow.graph import graph
            config = {"configurable": {"thread_id": session.id}}
            values = {
                "ats_score": ats_score_val,
                "optimized_resume": optimized_resume_val,
                "resume_text": optimized_resume_val,
                "optimization_recommended": False,
                "generated_document_path": generated_document_path,
                "email_payload": email_draft_val,
                "workflow_status": "draft_ready_for_human_review",
            }
            await graph.aupdate_state(config, values, as_node="check_ats_threshold")
            await graph.ainvoke(None, config=config)
        except Exception:
            pass

    elif payload.action == "proceed_as_is":
        session.status = "draft_ready_for_human_review"
        state = dict(session.state_json or {})
        state["optimization_recommended"] = False
        state["approve_optimization"] = False
        
        # Save to resume version metadata too
        resume_version.metadata_json = {
            **(resume_version.metadata_json or {}),
            "approve_optimization": False
        }
        db.add(resume_version)
        db.commit()

        ats_score_val = state.get("ats_score")
        optimized_resume_val = resume_version.raw_text
        
        # Find original file copy
        import glob
        original_files = glob.glob(f"storage_workspace/uploads/user_{resume_version.user_id}_original.*")
        if original_files:
            generated_document_path = str(Path(original_files[0]).resolve())
        else:
            generated_document_path = resume_version.metadata_json.get("stored_path")
            
        # Re-draft cover letter and email payload using original unoptimized resume
        outreach_agent = OutreachAgent()
        cover_letter = await outreach_agent.draft_cover_letter(
            resume_text=optimized_resume_val,
            job_description=job_target.job_description,
            company_name=job_target.company_name,
        )
        email_payload = outreach_agent.build_email_payload(
            recipient_email=state.get("email_draft", {}).get("recipient_email") or "review-before-send@example.com",
            subject=f"Application for {job_target.role_title} at {job_target.company_name}",
            body=cover_letter,
            attachments=[generated_document_path] if generated_document_path else [],
            metadata={
                "resume_version_id": resume_version.id,
                "job_target_id": job_target.id,
                "candidate_preference_id": preference.id if preference else None,
                "skills_to_highlight": selected_skills,
                "requires_hitl_gate": "gate-3",
            },
        )
        email_draft_val = asdict(email_payload)

        state["optimized_resume"] = optimized_resume_val
        state["generated_document_path"] = generated_document_path
        state["email_draft"] = email_draft_val
        state["email_payload"] = email_draft_val
        session.state_json = state
        db.commit()

        try:
            from src.workflow.graph import graph
            config = {"configurable": {"thread_id": session.id}}
            values = {
                "optimization_recommended": False,
                "approve_optimization": False,
                "workflow_status": "draft_ready_for_human_review",
                "optimized_resume": optimized_resume_val,
                "generated_document_path": generated_document_path,
                "email_payload": email_draft_val,
            }
            await graph.aupdate_state(config, values, as_node="check_ats_threshold")
            resumed_state = await graph.ainvoke(None, config=config)
            if isinstance(resumed_state, dict):
                session.state_json = dict(resumed_state)
                db.commit()
                ats_score_val = resumed_state.get("ats_score", ats_score_val)
                optimized_resume_val = resumed_state.get("optimized_resume", optimized_resume_val)
                email_draft_val = resumed_state.get("email_payload") or resumed_state.get("email_draft") or email_draft_val
                generated_document_path = resumed_state.get("generated_document_path", generated_document_path)
        except Exception:
            pass

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported action: {payload.action}",
        )

    return {
        "status": "draft_ready_for_human_review",
        "session_id": session.id,
        "resume_version_id": session.resume_version_id,
        "job_target_id": session.job_target_id,
        "ats_score": ats_score_val,
        "optimized_resume": optimized_resume_val,
        "email_draft": email_draft_val,
        "generated_pdf": generated_document_path,
        "hitl_gate": {
            "gate": "gate-3",
            "message": "Review optimized resume and email draft before dispatch.",
            "approval_endpoint": "/api/v1/hitl/gate-3",
            "approval_payload": {
                "session_id": session.id,
                "approved": True,
                "reviewer_email": None,
                "notes": "Approved optimized resume and email draft.",
            },
        },
    }


class HitlDecisionRequest(BaseModel):
    thread_id: str
    action: str | None = None
    approve_optimization: bool | None = None


@router.post("/decision")
async def handle_hitl_decision(payload: HitlDecisionRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    session = db.get(WorkflowSession, payload.thread_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow session not found.",
        )

    action = payload.action
    if not action and payload.approve_optimization is not None:
        action = "optimize" if payload.approve_optimization else "keep_original"

    if action not in ["optimize", "keep_original", "switch_to_scratch"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {action}. Must be one of optimize, keep_original, switch_to_scratch",
        )

    if action == "optimize":
        state = session.state_json or {}
        ats_score = state.get("ats_score", 0.0)
        if ats_score <= 1.0:
            ats_score *= 100.0
        intake_mode = state.get("intake_mode", "upload")
        
        if intake_mode == "upload" and ats_score < 80:
            from src.utils.docx_compiler import DocxCompiler
            from src.schemas.resume import validate_resume_info_density
            resume_text = state.get("resume_text", "")
            parsed_dict = DocxCompiler().parse_resume_text_to_dict(resume_text)
            has_sufficient_info, missing_fields = validate_resume_info_density(parsed_dict)
            if not has_sufficient_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The uploaded resume has an ATS score below 80% and has insufficient information. "
                           "Optimization is not allowed to prevent generating fake/default information. "
                           "Please choose the 'switch_to_scratch' option to build your resume from scratch.",
                )

    from src.workflow.graph import graph
    from langgraph.types import Command

    config = {"configurable": {"thread_id": payload.thread_id}}

    resumed_state = await graph.ainvoke(Command(resume=action), config=config)

    if isinstance(resumed_state, dict):
        session.state_json = dict(resumed_state)
        session.status = resumed_state.get("workflow_status") or "running"
        db.commit()
    else:
        resumed_state = dict(session.state_json or {})

    try:
        from src.api.progress import progress_hub
        await progress_hub.publish(
            payload.thread_id,
            {"type": "workflow_state", "workflow_status": resumed_state.get("workflow_status"), "state": resumed_state},
        )
    except Exception:
        pass

    return {
        "session_id": payload.thread_id,
        "workflow_status": resumed_state.get("workflow_status"),
        "ats_score": resumed_state.get("ats_score"),
        "optimized_resume": resumed_state.get("optimized_resume"),
        "email_draft": resumed_state.get("email_payload") or resumed_state.get("email_draft"),
        "generated_pdf": resumed_state.get("generated_document_path"),
        "approve_optimization": resumed_state.get("approve_optimization"),
        "intake_mode": resumed_state.get("intake_mode"),
        "recommendation": resumed_state.get("recommendation"),
    }
