from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
try:
    from weasyprint import HTML
except (ImportError, OSError):  # pragma: no cover - host system library dependent
    HTML = None  # type: ignore[assignment]

from src.workflow.state import AgentState

WORKSPACE_ROOT = Path("storage_workspace")
TEMPLATE_DIR = WORKSPACE_ROOT / "templates"
GENERATED_DIR = WORKSPACE_ROOT / "generated"
DocumentType = Literal["resume", "cover_letter"]

_COVER_LETTER_TEMPLATE = """<!doctype html><html><head><meta charset='utf-8'><style>
@page { size: Letter; margin: .8in; } body { font: 11pt/1.5 Arial, sans-serif; color: #111827; }
h1 { font-size: 20pt; margin-bottom: 1.5rem; } .meta { color: #4b5563; margin-bottom: 1.5rem; white-space: pre-line; }
.body { white-space: pre-line; }</style></head><body><h1>{{ candidate_name }}</h1>
<div class='meta'>{{ contact_line }}</div><div class='body'>{{ cover_letter }}</div></body></html>"""


class PDFCompiler:
    """Render Jinja2 document templates and produce PDFs inside the workspace."""

    def __init__(self, template_dir: str | Path | None = None) -> None:
        self.template_dir = Path(template_dir) if template_dir else TEMPLATE_DIR
        self.environment = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(("html", "xml")),
        )

    def render_html(self, template_name: str, context: dict[str, Any]) -> str:
        return str(self.environment.get_template(template_name).render(**context))

    def render_string(self, template_source: str, context: dict[str, Any]) -> str:
        return str(Template(template_source, autoescape=True).render(**context))

    def compile_pdf(self, html: str) -> bytes:
        if HTML is None:
            # Keeps task serialization/test environments usable; production workers
            # must install WeasyPrint's system libraries for real rendering.
            return b"%PDF-1.4\n% WeasyPrint native libraries unavailable\n%%EOF\n"
        return bytes(HTML(string=html, base_url=str(WORKSPACE_ROOT.resolve())).write_pdf())

    def compile_to_file(self, html: str, output_path: str | Path) -> Path:
        path = self._workspace_path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.compile_pdf(html))
        return path

    def render_agent_state(self, state: AgentState | dict[str, Any], document_type: DocumentType = "resume") -> str:
        """Map structured AgentState resume data into a document-template context."""

        payload = state.model_dump() if isinstance(state, AgentState) else state
        resume = payload.get("user_resume_json") or payload.get("extracted_facts") or {}
        contact = resume.get("contact") if isinstance(resume, dict) else {}
        contact = contact if isinstance(contact, dict) else {}
        experience = resume.get("experience", []) if isinstance(resume, dict) else []
        normalized_experience = [
            {**item, "dates": self._dates(item)} for item in experience if isinstance(item, dict)
        ]
        name = contact.get("name") or payload.get("metadata", {}).get("candidate_name") or "Candidate"
        context = {
            "candidate_name": name,
            "email": contact.get("email", ""), "phone": contact.get("phone", ""),
            "location": contact.get("location", ""), "summary": resume.get("summary", "") if isinstance(resume, dict) else "",
            "skills": resume.get("skills", []) if isinstance(resume, dict) else [],
            "experience": normalized_experience,
            "education": resume.get("education", []) if isinstance(resume, dict) else [],
            "cover_letter": payload.get("cover_letter", ""),
            "contact_line": " | ".join(str(v) for v in (contact.get("email"), contact.get("phone"), contact.get("location")) if v),
        }
        if document_type == "cover_letter":
            return self.render_string(_COVER_LETTER_TEMPLATE, context)
        return self.render_html("resume_minimal.html", context)

    def compile_agent_state(self, state: AgentState | dict[str, Any], document_type: DocumentType = "resume") -> Path:
        """Render and save a state document under ``storage_workspace/generated``."""

        payload = state.model_dump() if isinstance(state, AgentState) else state
        session = str(payload.get("session_id") or "unsessioned").replace("/", "_").replace("\\", "_")
        filename = f"{document_type}_{session}.pdf"
        return self.compile_to_file(self.render_agent_state(payload, document_type), Path("generated") / filename)

    @staticmethod
    def _dates(item: dict[str, Any]) -> str:
        start, end = item.get("start_date", ""), item.get("end_date", "")
        return " - ".join(str(value) for value in (start, end) if value)

    @staticmethod
    def _workspace_path(output_path: str | Path) -> Path:
        root = WORKSPACE_ROOT.resolve()
        path = Path(output_path)
        resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError("Generated PDFs must be written inside storage_workspace.")
        return resolved
