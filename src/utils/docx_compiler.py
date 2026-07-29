# File: src/utils/docx_compiler.py
"""Word Document compiler for resume and cover letter generation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

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
        """Add uppercase section title with horizontal divider line."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        
        run = p.add_run(title)
        run.bold = True
        run.font.name = 'Arial'
        run.font.size = Pt(11.5)
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

        # XML Paragraph bottom border for perfect solid lines
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')  # 6/8 pt = 0.75 pt
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), '333333')
        pBdr.append(bottom)
        pPr.append(pBdr)

    def parse_resume_text_to_dict(self, text: str) -> dict[str, Any]:
        """Parse raw resume text (with headings and divider lines) into a structured dictionary."""
        data = {
            "contact": {
                "name": "Candidate",
                "email": "",
                "phone": "",
                "location": "",
                "linkedin": "",
                "github": "",
                "portfolio": ""
            },
            "subtitle": "",
            "summary": "",
            "experience": [],
            "skills": [],
            "education": [],
            "projects": [],
            "certifications": [],
            "achievements": []
        }

        if not text:
            return data

        lines = [line.strip() for line in text.splitlines()]

        # 1. Parse header (up to the first section header or divider)
        header_lines = []
        section_start_idx = 0
        for i, line in enumerate(lines):
            is_div = line == "---" or re.match(r'^[-=*_]+$', line)
            is_hdr = any(s in line.upper() for s in ["EDUCATION", "EXPERIENCE", "PROJECTS", "SKILLS", "ACHIEVEMENTS", "SUMMARY", "EXTRACURRICULAR"]) and len(line) < 40
            if is_div or is_hdr:
                section_start_idx = i
                break
            if line:
                header_lines.append(line)

        if header_lines:
            data["contact"]["name"] = header_lines[0]
            for hl in header_lines[1:]:
                is_contact = False
                for k in ["phone", "email", "location", "github", "linkedin", "portfolio", "http", "https", "@", "|"]:
                    if k in hl.lower():
                        is_contact = True
                        break
                if re.search(r'\+?\d[\d\s\-()]{8,15}\d', hl):
                    is_contact = True

                if not is_contact:
                    if not data["subtitle"] and len(hl) < 60:
                        data["subtitle"] = hl
                        continue
                
                parts = [p.strip() for p in re.split(r'\||•|·', hl)]
                for p in parts:
                    if "@" in p:
                        m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', p)
                        if m:
                            data["contact"]["email"] = m.group(0)
                    elif re.search(r'\+?\d[\d\s\-()]{8,15}\d', p):
                        m = re.search(r'(\+?\d[\d\s\-()]{8,15}\d)', p)
                        if m:
                            data["contact"]["phone"] = m.group(0)
                    elif any(domain in p.lower() for domain in ["linkedin.com", "linkedin", "in/"]):
                        data["contact"]["linkedin"] = p
                    elif any(domain in p.lower() for domain in ["github.com", "github"]):
                        data["contact"]["github"] = p
                    elif any(domain in p.lower() for domain in ["portfolio", "website", "http", "https"]):
                        data["contact"]["portfolio"] = p
                    elif len(p) > 3 and not data["contact"]["location"]:
                        data["contact"]["location"] = p

        # 2. Extract sections
        current_section = None
        section_content = []
        sections = {}

        for line in lines[section_start_idx:]:
            if line == "---" or re.match(r'^[-=*_]+$', line):
                continue
            
            line_upper = line.upper().replace("&", "AND").replace("AND EXTRACURRICULARS", "").replace("AND EXTRACURRICULAR", "")
            is_header = False
            header_name = None
            for s in ["EDUCATION", "EXPERIENCE", "PROFESSIONAL EXPERIENCE", "WORK EXPERIENCE", "PROJECTS", "SKILLS", "ACHIEVEMENTS", "SUMMARY", "PROFILE SUMMARY", "EXTRACURRICULARS", "EXTRACURRICULAR", "ONLINE COURSES", "CERTIFICATIONS"]:
                if s in line_upper and len(line) < 40:
                    is_header = True
                    header_name = s
                    break

            if is_header:
                if current_section:
                    sections[current_section] = section_content
                current_section = header_name
                section_content = []
            else:
                if current_section and line:
                    section_content.append(line)

        if current_section:
            sections[current_section] = section_content

        # 3. Parse sections content
        # Profile Summary
        sum_lines = sections.get("SUMMARY") or sections.get("PROFILE SUMMARY") or []
        data["summary"] = " ".join(sum_lines)

        # Skills
        sk_lines = sections.get("SKILLS") or []
        for sl in sk_lines:
            if ":" in sl:
                parts = sl.split(":", 1)
                cat = parts[0].strip().lstrip("-*•· ").strip()
                items = [item.strip() for item in parts[1].split(",") if item.strip()]
                data["skills"].append({"category": cat, "items": items})
            else:
                cleaned = sl.lstrip("-*•· ").strip()
                if cleaned:
                    data["skills"].append(cleaned)

        # Experience
        exp_lines = sections.get("EXPERIENCE") or sections.get("PROFESSIONAL EXPERIENCE") or sections.get("WORK EXPERIENCE") or []
        current_entry = None
        for el in exp_lines:
            if el.startswith("•") or el.startswith("-") or el.startswith("*") or el.startswith("·"):
                if current_entry:
                    current_entry["bullets"].append(el.lstrip("-*•· ").strip())
            else:
                if current_entry:
                    data["experience"].append(current_entry)
                
                parts = [p.strip() for p in re.split(r'\||\t|  {3,}', el)]
                role = parts[0] if len(parts) > 0 else "Developer"
                company = parts[1] if len(parts) > 1 else ""
                location = parts[2] if len(parts) > 2 else ""
                dates = parts[3] if len(parts) > 3 else ""
                
                current_entry = {
                    "role": role,
                    "company": company,
                    "location": location,
                    "dates": dates,
                    "bullets": []
                }
        if current_entry:
            data["experience"].append(current_entry)

        # Projects
        proj_lines = sections.get("PROJECTS") or []
        current_proj = None
        for pl in proj_lines:
            if pl.startswith("•") or pl.startswith("-") or pl.startswith("*") or pl.startswith("·"):
                if current_proj:
                    current_proj["bullets"].append(pl.lstrip("-*•· ").strip())
            else:
                if current_proj:
                    data["projects"].append(current_proj)
                
                parts = [p.strip() for p in re.split(r'\||\t|  {3,}', pl)]
                name = parts[0] if len(parts) > 0 else "Project"
                tech = parts[1] if len(parts) > 1 else ""
                dates = parts[2] if len(parts) > 2 else ""
                
                current_proj = {
                    "name": name,
                    "technologies": tech,
                    "dates": dates,
                    "bullets": []
                }
        if current_proj:
            data["projects"].append(current_proj)

        # Education
        edu_lines = sections.get("EDUCATION") or []
        current_edu = None
        for edl in edu_lines:
            if any(k in edl.lower() for k in ["bachelor", "b.tech", "degree", "master", "m.tech", "12th", "10th", "school", "university", "technology"]):
                if current_edu:
                    data["education"].append(current_edu)
                
                parts = [p.strip() for p in re.split(r'\||\t|  {3,}', edl)]
                degree = parts[0]
                institution = parts[1] if len(parts) > 1 else ""
                location = parts[2] if len(parts) > 2 else ""
                dates = parts[3] if len(parts) > 3 else ""
                grade = parts[4] if len(parts) > 4 else ""
                
                current_edu = {
                    "degree": degree,
                    "institution": institution,
                    "location": location,
                    "dates": dates,
                    "grade": grade
                }
            elif current_edu:
                if not current_edu["institution"]:
                    current_edu["institution"] = edl
                elif not current_edu["dates"] and re.search(r'\d{4}', edl):
                    current_edu["dates"] = edl
                elif not current_edu["grade"] and any(k in edl.lower() for k in ["gpa", "cgpa", "%", "percent", "grade"]):
                    current_edu["grade"] = edl
                
        if current_edu:
            data["education"].append(current_edu)

        # Achievements
        ach_lines = sections.get("ACHIEVEMENTS") or sections.get("EXTRACURRICULARS") or sections.get("EXTRACURRICULAR") or []
        for al in ach_lines:
            cleaned = al.lstrip("-*•· ").strip()
            if cleaned:
                data["achievements"].append(cleaned)

        # Certifications
        cert_lines = sections.get("CERTIFICATIONS") or sections.get("ONLINE COURSES") or []
        for cl in cert_lines:
            cleaned = cl.lstrip("-*•· ").strip()
            if cleaned:
                data["certifications"].append(cleaned)

        return data

    def render_official_ats_docx(self, candidate_data: dict, user_id: int, version: int) -> str:
        """Render candidate resume JSON into official, ATS-friendly Word document following Abhishek Sharma structure."""
        doc = self._setup_document()
        from docx.enum.text import WD_TAB_ALIGNMENT

        contact = candidate_data.get("contact") or {}
        name = contact.get("name") or "Abhishek Sharma"
        subtitle = candidate_data.get("subtitle") or contact.get("role") or ""
        
        # 1. HEADER (Name, Subtitle, Contact Details)
        header_p = doc.add_paragraph()
        header_p.alignment = 1  # Center
        header_p.paragraph_format.space_before = Pt(0)
        header_p.paragraph_format.space_after = Pt(2)
        
        run_name = header_p.add_run(name)
        run_name.bold = True
        run_name.font.name = 'Arial'
        run_name.font.size = Pt(18)
        run_name.font.color.rgb = RGBColor(0, 0, 0)

        if subtitle:
            sub_p = doc.add_paragraph()
            sub_p.alignment = 1  # Center
            sub_p.paragraph_format.space_before = Pt(0)
            sub_p.paragraph_format.space_after = Pt(4)
            run_sub = sub_p.add_run(subtitle)
            run_sub.bold = True
            run_sub.font.name = 'Arial'
            run_sub.font.size = Pt(11)
            run_sub.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

        # Contact line
        contact_parts = []
        
        phone = contact.get("phone")
        if phone:
            contact_parts.append(f"📞 {phone}")
            
        email = contact.get("email")
        if email:
            contact_parts.append(f"✉️ {email}")
            
        location = contact.get("location")
        if location:
            contact_parts.append(f"📍 {location}")
            
        linkedin = contact.get("linkedin")
        if linkedin:
            clean_linkedin = linkedin.replace("https://", "").replace("http://", "").replace("linkedin.com/in/", "").replace("linkedin.com/", "")
            contact_parts.append(f"🔗 in/{clean_linkedin}")
            
        github = contact.get("github")
        if github:
            clean_github = github.replace("https://", "").replace("http://", "").replace("github.com/", "")
            contact_parts.append(f"💻 github.com/{clean_github}")
            
        portfolio = contact.get("portfolio") or contact.get("website")
        if portfolio:
            clean_port = portfolio.replace("https://", "").replace("http://", "")
            contact_parts.append(f"🌐 {clean_port}")

        contact_line = "  |  ".join(contact_parts)
        if contact_line:
            contact_p = doc.add_paragraph()
            contact_p.alignment = 1  # Center
            contact_p.paragraph_format.space_before = Pt(0)
            contact_p.paragraph_format.space_after = Pt(12)
            run_contact = contact_p.add_run(contact_line)
            run_contact.font.name = 'Arial'
            run_contact.font.size = Pt(9.5)
            run_contact.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

        # 2. PROFILE SUMMARY
        summary = candidate_data.get("summary")
        if summary:
            self._add_section_title(doc, "Profile Summary")
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            p.alignment = 3  # Justify
            run_sum = p.add_run(summary)
            run_sum.font.name = 'Arial'
            run_sum.font.size = Pt(10)

        # 3. PROFESSIONAL EXPERIENCE
        experience = candidate_data.get("experience")
        if experience:
            self._add_section_title(doc, "Professional Experience")
            for exp in experience:
                role = exp.get("role") or "Software Engineer"
                company = exp.get("company") or ""
                loc = exp.get("location") or ""
                dates = exp.get("dates") or exp.get("start_date") or ""
                if not dates:
                    start = exp.get("start_date") or ""
                    end = exp.get("end_date") or ""
                    dates = f"{start} - {end}" if start and end else (start or end)
                
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                
                p.paragraph_format.tab_stops.add_tab_stop(Inches(7.3), WD_TAB_ALIGNMENT.RIGHT)
                
                run_role = p.add_run(role)
                run_role.bold = True
                run_role.font.name = 'Arial'
                run_role.font.size = Pt(10)
                
                if company:
                    p.add_run(", ")
                    run_comp = p.add_run(f"({company})")
                    run_comp.italic = True
                    run_comp.font.name = 'Arial'
                    run_comp.font.size = Pt(10)
                    run_comp.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
                    
                p.add_run("\t")
                
                loc_dates_parts = [v for v in [loc, dates] if v]
                loc_dates_str = "   ".join(loc_dates_parts)
                
                run_right = p.add_run(loc_dates_str)
                run_right.font.name = 'Arial'
                run_right.font.size = Pt(9.5)
                run_right.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
                
                bullets = exp.get("bullets") or []
                desc = exp.get("description") or ""
                if not bullets and desc:
                    bullets = [b.strip().lstrip("-*•·").strip() for b in desc.split("\n") if b.strip()]
                    
                for b in bullets:
                    bp = doc.add_paragraph(style="List Bullet")
                    bp.paragraph_format.space_before = Pt(0)
                    bp.paragraph_format.space_after = Pt(2)
                    
                    m = re.match(r'^(\*\*[^*]+\*\*)(.*)$', b)
                    if m:
                        verb = m.group(1).replace("**", "")
                        rest = m.group(2)
                        rv = bp.add_run(verb)
                        rv.bold = True
                        rv.font.name = 'Arial'
                        rv.font.size = Pt(9.5)
                        rr = bp.add_run(rest)
                        rr.font.name = 'Arial'
                        rr.font.size = Pt(9.5)
                    else:
                        words = b.split(" ", 1)
                        if len(words) > 1 and re.match(r'^[A-Z][a-z]+$', words[0]):
                            rv = bp.add_run(words[0] + " ")
                            rv.bold = True
                            rv.font.name = 'Arial'
                            rv.font.size = Pt(9.5)
                            rr = bp.add_run(words[1])
                            rr.font.name = 'Arial'
                            rr.font.size = Pt(9.5)
                        else:
                            run_b = bp.add_run(b)
                            run_b.font.name = 'Arial'
                            run_b.font.size = Pt(9.5)

        # 4. SKILLS
        skills = candidate_data.get("skills")
        if skills:
            self._add_section_title(doc, "Skills")
            for sk in skills:
                bp = doc.add_paragraph(style="List Bullet")
                bp.paragraph_format.space_before = Pt(0)
                bp.paragraph_format.space_after = Pt(2)
                
                if isinstance(sk, dict) and "category" in sk:
                    cat = sk["category"]
                    items = ", ".join(sk["items"]) if isinstance(sk["items"], list) else str(sk["items"])
                    
                    run_cat = bp.add_run(f"{cat}: ")
                    run_cat.bold = True
                    run_cat.font.name = 'Arial'
                    run_cat.font.size = Pt(9.5)
                    
                    run_items = bp.add_run(items)
                    run_items.font.name = 'Arial'
                    run_items.font.size = Pt(9.5)
                else:
                    run_sk = bp.add_run(str(sk))
                    run_sk.font.name = 'Arial'
                    run_sk.font.size = Pt(9.5)

        # 5. EDUCATION
        education = candidate_data.get("education")
        if education:
            self._add_section_title(doc, "Education")
            for edu in education:
                deg = edu.get("degree") or "Degree"
                inst = edu.get("institution") or edu.get("school") or ""
                loc = edu.get("location") or ""
                dates = edu.get("dates") or edu.get("start_date") or ""
                if not dates:
                    start = edu.get("start_date") or ""
                    end = edu.get("end_date") or ""
                    dates = f"{start} - {end}" if start and end else (start or end)
                grade = edu.get("grade") or edu.get("gpa") or ""
                
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.tab_stops.add_tab_stop(Inches(7.3), WD_TAB_ALIGNMENT.RIGHT)
                
                run_deg = p.add_run(deg)
                run_deg.bold = True
                run_deg.font.name = 'Arial'
                run_deg.font.size = Pt(10)
                
                if inst:
                    p.add_run("   ")
                    inst_loc = f"{inst}, {loc}" if loc else inst
                    run_inst = p.add_run(inst_loc)
                    run_inst.italic = True
                    run_inst.font.name = 'Arial'
                    run_inst.font.size = Pt(10)
                    run_inst.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
                    
                if grade:
                    p.add_run("   ")
                    run_grade = p.add_run(grade)
                    run_grade.bold = True
                    run_grade.font.name = 'Arial'
                    run_grade.font.size = Pt(10)
                    
                p.add_run("\t")
                run_dates = p.add_run(dates)
                run_dates.font.name = 'Arial'
                run_dates.font.size = Pt(9.5)
                run_dates.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

        # 6. PROJECTS
        projects = candidate_data.get("projects")
        if projects:
            self._add_section_title(doc, "Projects")
            for proj in projects:
                name = proj.get("name") or "Project"
                tech = proj.get("technologies") or ""
                dates = proj.get("dates") or ""
                link = proj.get("link") or proj.get("url") or ""
                
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                p.paragraph_format.tab_stops.add_tab_stop(Inches(7.3), WD_TAB_ALIGNMENT.RIGHT)
                
                run_name = p.add_run(name)
                run_name.bold = True
                run_name.font.name = 'Arial'
                run_name.font.size = Pt(10)
                
                if link:
                    p.add_run("  ")
                    run_link = p.add_run("Link")
                    run_link.underline = True
                    run_link.font.name = 'Arial'
                    run_link.font.size = Pt(10)
                    run_link.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
                    
                if tech:
                    p.add_run("   ")
                    run_tech = p.add_run(tech)
                    run_tech.font.name = 'Arial'
                    run_tech.font.size = Pt(9.5)
                    run_tech.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)
                    
                p.add_run("\t")
                run_dates = p.add_run(dates)
                run_dates.font.name = 'Arial'
                run_dates.font.size = Pt(9.5)
                run_dates.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
                
                bullets = proj.get("bullets") or []
                desc = proj.get("description") or ""
                if not bullets and desc:
                    bullets = [b.strip().lstrip("-*•·").strip() for b in desc.split("\n") if b.strip()]
                    
                for b in bullets:
                    bp = doc.add_paragraph(style="List Bullet")
                    bp.paragraph_format.space_before = Pt(0)
                    bp.paragraph_format.space_after = Pt(2)
                    
                    m = re.match(r'^(\*\*[^*]+\*\*)(.*)$', b)
                    if m:
                        verb = m.group(1).replace("**", "")
                        rest = m.group(2)
                        rv = bp.add_run(verb)
                        rv.bold = True
                        rv.font.name = 'Arial'
                        rv.font.size = Pt(9.5)
                        rr = bp.add_run(rest)
                        rr.font.name = 'Arial'
                        rr.font.size = Pt(9.5)
                    else:
                        words = b.split(" ", 1)
                        if len(words) > 1 and re.match(r'^[A-Z][a-z]+$', words[0]):
                            rv = bp.add_run(words[0] + " ")
                            rv.bold = True
                            rv.font.name = 'Arial'
                            rv.font.size = Pt(9.5)
                            rr = bp.add_run(words[1])
                            rr.font.name = 'Arial'
                            rr.font.size = Pt(9.5)
                        else:
                            run_b = bp.add_run(b)
                            run_b.font.name = 'Arial'
                            run_b.font.size = Pt(9.5)

        # 7. ONLINE COURSES & CERTIFICATIONS
        certs = candidate_data.get("certifications") or candidate_data.get("courses")
        if certs:
            self._add_section_title(doc, "Online Courses & Certifications")
            for c in certs:
                bp = doc.add_paragraph(style="List Bullet")
                bp.paragraph_format.space_before = Pt(0)
                bp.paragraph_format.space_after = Pt(2)
                
                run_c = bp.add_run(str(c))
                run_c.font.name = 'Arial'
                run_c.font.size = Pt(9.5)

        # 8. ACHIEVEMENTS & EXTRACURRICULAR
        ach = candidate_data.get("achievements")
        if ach:
            self._add_section_title(doc, "Achievements & Extracurricular")
            for a in ach:
                bp = doc.add_paragraph(style="List Bullet")
                bp.paragraph_format.space_before = Pt(0)
                bp.paragraph_format.space_after = Pt(2)
                
                run_a = bp.add_run(str(a))
                run_a.font.name = 'Arial'
                run_a.font.size = Pt(9.5)

        output_filename = f"final_documents/user_{user_id}/resume_v{version}.docx"
        output_path = WORKSPACE_ROOT / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path.resolve()))
        return str(output_path.resolve())

    def compile_docx_state(self, state: dict[str, Any], output_path: str | Path) -> Path:
        """Compile a state JSON resume into a professional Word docx file."""
        resume = state.get("optimized_resume_json") or state.get("user_resume_json") or state.get("extracted_facts") or {}
        raw_text = state.get("optimized_resume") or state.get("resume_text") or ""
        
        # Determine if we should parse raw text instead of dummy dictionary
        if isinstance(resume, str):
            resume = self.parse_resume_text_to_dict(resume)
        elif isinstance(resume, dict):
            exp = resume.get("experience") or []
            if len(exp) == 1 and "EDUCATION" in (exp[0].get("description") or ""):
                resume = self.parse_resume_text_to_dict(exp[0].get("description"))
            elif not resume or (not resume.get("experience") and not resume.get("projects") and raw_text):
                resume = self.parse_resume_text_to_dict(raw_text)
        else:
            resume = self.parse_resume_text_to_dict(raw_text)
                
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
