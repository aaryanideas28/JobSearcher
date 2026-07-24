# File: src/utils/pdf_compiler.py
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, Template
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]
    Template = None  # type: ignore[assignment]

try:
    from weasyprint import HTML
except (ImportError, OSError):  # pragma: no cover - dependency bootstrap fallback
    HTML = None  # type: ignore[assignment]


class PDFCompiler:
    """Render resume templates with Jinja2 and compile them to PDF bytes."""

    def __init__(self, template_dir: str | Path | None = None) -> None:
        self.template_dir = Path(template_dir) if template_dir else None
        self.environment = self._build_environment()

    def render_html(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template into HTML."""

        if self.environment is not None:
            template = self.environment.get_template(template_name)
            return str(template.render(**context))
        return str(context.get("body", ""))

    def render_string(self, template_source: str, context: dict[str, Any]) -> str:
        """Render an inline Jinja2 template string."""

        if Template is not None:
            return str(Template(template_source).render(**context))
        rendered = template_source
        for key, value in context.items():
            rendered = rendered.replace("{{ " + key + " }}", str(value))
            rendered = rendered.replace("{{" + key + "}}", str(value))
        return rendered

    def compile_pdf(self, html: str) -> bytes:
        """Compile HTML into PDF bytes."""

        if HTML is None:
            return b"%PDF-1.4\n% scaffold placeholder\n%%EOF\n"
        return bytes(HTML(string=html).write_pdf())

    def compile_to_file(self, html: str, output_path: str | Path) -> Path:
        """Compile HTML and write the resulting PDF to disk."""

        path = Path(output_path)
        path.write_bytes(self.compile_pdf(html))
        return path

    def _build_environment(self) -> Any | None:
        """Create a Jinja2 environment when the dependency and template directory exist."""

        if Environment is None or FileSystemLoader is None or self.template_dir is None:
            return None
        return Environment(loader=FileSystemLoader(str(self.template_dir)), autoescape=True)
