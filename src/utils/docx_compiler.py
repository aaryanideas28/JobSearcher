# File: src/utils/docx_compiler.py
"""Word Document compiler for resume and cover letter generation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
import docx
from docx.shared import Pt, Inches, RGBColor

from src.workflow.state import AgentState

WORKSPACE_ROOT = Path("storage_workspace")
TEMPLATE_DIR = WORKSPACE_ROOT / "templates"
GENERATED_DIR = WORKSPACE_ROOT / "generated"

class DocxCompiler:
    """Render documents directly into Microsoft Word docx format inside the workspace."""

    def __init__(self, template_dir: str | Path | None = None) -> None:
        self.template_dir = Path(template_dir) if template_dir else TEMPLATE_DIR

    def _setup_document(self) -> docx.Document:
        """Create a document with 0.6-inch margins and base Arial style."""
        doc = docx.Document()
        for section in doc.sections:
            section.top_margin = Inches(0.6)
            section.bottom_margin = Inches(0.6)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)
            
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(10)
        font.color.rgb = RGBColor(0x11, 0x11, 0x11)
        
        return doc

    def _add_section_title(self, doc: docx.Document, title: str):
        """Add uppercase section title in 11pt bold Arial `#000000` with spacing and keep_with_next."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        
        run = p.add_run(title.upper())
        run.bold = True
        run.font.name = 'Arial'
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    def render_official_ats_docx(self, candidate_data: dict, user_id: int, version: int) -> str:
        """Render candidate resume JSON into official, ATS-friendly Word document."""
        doc = self._setup_document()

        contact = candidate_data.get("contact") or {}
        name = contact.get("name") or "Candidate"
        
        header_p = doc.add_paragraph()
        header_p.alignment = 1  # Center
        header_p.paragraph_format.space_after = Pt(2)
        
        run_name = header_p.add_run(name)
        run_name.bold = True
        run_name.font.name = 'Arial'
        run_name.font.size = Pt(18)
        run_name.font.color.rgb = RGBColor(0x11, 0x11, 0x11)

        contact_parts = []
        for key in ["email", "phone", "location", "github", "linkedin"]:
            val = contact.get(key)
            if val:
                contact_parts.append(str(val))
        
        contact_line = " | ".join(contact_parts)
        if contact_line:
            contact_p = doc.add_paragraph()
            contact_p.alignment = 1  # Center
            contact_p.paragraph_format.space_after = Pt(12)
            run_contact = contact_p.add_run(contact_line)
            run_contact.font.name = 'Arial'
            run_contact.font.size = Pt(9.5)
            run_contact.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)

        summary = candidate_data.get("summary")
        if summary:
            self._add_section_title(doc, "Professional Summary")
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.15
            run = p.add_run(summary)
            run.font.name = 'Arial'
            run.font.size = Pt(10)

        skills = candidate_data.get("skills")
        if skills:
            self._add_section_title(doc, "Technical Skills")
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
            run = p.add_run(skills_str)
            run.font.name = 'Arial'
            run.font.size = Pt(10)

        experience = candidate_data.get("experience")
        if experience:
            self._add_section_title(doc, "Work Experience")
            for exp in experience:
                role = exp.get("role") or exp.get("title") or "Role"
                company = exp.get("company", "Company")
                start = exp.get("start_date") or ""
                end = exp.get("end_date") or ""
                dates = " - ".join(str(v) for v in (start, end) if v)
                
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                
                run_role = p.add_run(f"{role} | {company}")
                run_role.bold = True
                run_role.font.name = 'Arial'
                run_role.font.size = Pt(10)
                
                if dates:
                    p.add_run("\t" * 3)
                    run_dates = p.add_run(dates)
                    run_dates.italic = True
                    run_dates.font.name = 'Arial'
                    run_dates.font.size = Pt(9.5)
                    run_dates.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)
                
                desc = exp.get("description", "")
                if desc:
                    lines = [line.strip().lstrip("-*•").strip() for line in desc.split("\n") if line.strip()]
                    for line in lines:
                        bullet_p = doc.add_paragraph(style="List Bullet")
                        bullet_p.paragraph_format.space_after = Pt(2)
                        run_bullet = bullet_p.add_run(line)
                        run_bullet.font.name = 'Arial'
                        run_bullet.font.size = Pt(10)

        projects = candidate_data.get("projects")
        if projects:
            self._add_section_title(doc, "Key Projects")
            for proj in projects:
                p_name = proj.get("name", "Project")
                desc = proj.get("description", "")
                
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                
                run_name = p.add_run(p_name)
                run_name.bold = True
                run_name.font.name = 'Arial'
                run_name.font.size = Pt(10)
                
                if desc:
                    lines = [line.strip().lstrip("-*•").strip() for line in desc.split("\n") if line.strip()]
                    for line in lines:
                        bullet_p = doc.add_paragraph(style="List Bullet")
                        bullet_p.paragraph_format.space_after = Pt(2)
                        run_bullet = bullet_p.add_run(line)
                        run_bullet.font.name = 'Arial'
                        run_bullet.font.size = Pt(10)

        education = candidate_data.get("education")
        if education:
            self._add_section_title(doc, "Education")
            for edu in education:
                inst = edu.get("institution") or edu.get("school") or "University"
                deg = edu.get("degree") or edu.get("major") or "Degree"
                start = edu.get("start_date") or ""
                end = edu.get("end_date") or ""
                dates = " - ".join(str(v) for v in (start, end) if v)
                
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                
                run_deg = p.add_run(f"{deg} - {inst}")
                run_deg.bold = True
                run_deg.font.name = 'Arial'
                run_deg.font.size = Pt(10)
                
                if dates:
                    p.add_run("\t" * 3)
                    run_dates = p.add_run(dates)
                    run_dates.font.name = 'Arial'
                    run_dates.font.size = Pt(9.5)
                    run_dates.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)

        output_filename = f"final_documents/user_{user_id}/resume_v{version}.docx"
        output_path = WORKSPACE_ROOT / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path.resolve()))
        return str(output_path.resolve())

    def compile_docx_state(self, state: dict[str, Any], output_path: str | Path) -> Path:
        """Compile a state JSON resume into a professional Word docx file."""
        resume = state.get("optimized_resume_json") or state.get("user_resume_json") or state.get("extracted_facts") or {}
        if isinstance(resume, str):
            try:
                import json
                resume = json.loads(resume)
            except Exception:
                resume = {}
                
        user_id = state.get("user_id") or 1
        attempt = state.get("attempt_count") or 1
        
        abs_path_str = self.render_official_ats_docx(resume, user_id, attempt)
        
        dest_path = self._workspace_path(output_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if str(dest_path.resolve()) != abs_path_str:
            import shutil
            shutil.copy2(abs_path_str, str(dest_path.resolve()))
            
        return dest_path

    def compile_agent_state(self, state: AgentState | dict[str, Any], document_type: str = "resume") -> Path:
        """Render and save a state document as docx under storage_workspace/final_documents or storage_workspace/generated."""
        payload = state.model_dump() if hasattr(state, "model_dump") else state
        user_id = payload.get("user_id") or 1
        attempt = payload.get("attempt_count") or 1

        if document_type == "resume":
            filename = f"final_documents/user_{user_id}/resume_v{attempt}.docx"
            return self.compile_docx_state(payload, filename)
        else:
            session = str(payload.get("session_id") or "unsessioned").replace("/", "_").replace("\\", "_")
            filename = f"generated/{document_type}_{session}.docx"
            return self.compile_docx_cover_letter(payload, filename)

    def compile_docx_cover_letter(self, state: dict[str, Any], output_path: str | Path) -> Path:
        """Compile cover letter text from state into a Word docx file."""
        doc = docx.Document()
        for section in doc.sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

        name = state.get("metadata", {}).get("candidate_name") or "Candidate"
        cover_letter_text = state.get("cover_letter", "") or state.get("cover_letter_text", "")

        p = doc.add_paragraph()
        run = p.add_run(name)
        run.bold = True
        run.font.name = 'Arial'
        run.font.size = Pt(16)
        run.font.color.rgb = RGBColor(17, 24, 39)

        body_p = doc.add_paragraph()
        body_p.paragraph_format.space_before = Pt(12)
        run_body = body_p.add_run(cover_letter_text)
        run_body.font.name = 'Arial'
        run_body.font.size = Pt(11)

        path = self._workspace_path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(path))
        return path

    @staticmethod
    def _workspace_path(output_path: str | Path) -> Path:
        root = WORKSPACE_ROOT.resolve()
        path = Path(output_path)
        resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
        if root not in resolved.parents and resolved != root:
            resolved = (root / path.name).resolve()
        return resolved
