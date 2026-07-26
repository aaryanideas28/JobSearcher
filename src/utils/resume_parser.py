# File: src/utils/resume_parser.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from docx import Document
except ImportError:  # pragma: no cover - optional dependency fallback
    Document = None  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency fallback
    PdfReader = None  # type: ignore[assignment]


@dataclass(slots=True)
class ParsedResume:
    """Parsed resume text and extraction metadata."""

    text: str
    source_path: Path
    parser: str
    warnings: list[str]


class ResumeParser:
    """Parse uploaded resume files into text for downstream AI workflows."""

    supported_suffixes: set[str] = {".txt", ".md", ".pdf", ".docx"}

    def parse(self, path: str | Path) -> ParsedResume:
        """Parse a supported resume file."""

        source_path = Path(path)
        suffix = source_path.suffix.lower()
        if suffix not in self.supported_suffixes:
            return ParsedResume(
                text="",
                source_path=source_path,
                parser="unsupported",
                warnings=[f"Unsupported resume type: {suffix or 'unknown'}"],
            )

        if suffix in {".txt", ".md"}:
            return self._parse_text(source_path)
        if suffix == ".pdf":
            return self._parse_pdf(source_path)
        return self._parse_docx(source_path)

    def _parse_text(self, path: Path) -> ParsedResume:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ParsedResume(text=text.strip(), source_path=path, parser="plain_text", warnings=[])

    def _parse_pdf(self, path: Path) -> ParsedResume:
        if PdfReader is None:
            return ParsedResume(
                text="",
                source_path=path,
                parser="pdf_unavailable",
                warnings=["Install pypdf to parse PDF resumes."],
            )

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return ParsedResume(text="\n".join(pages).strip(), source_path=path, parser="pypdf", warnings=[])

    def _parse_docx(self, path: Path) -> ParsedResume:
        if Document is None:
            return ParsedResume(
                text="",
                source_path=path,
                parser="docx_unavailable",
                warnings=["Install python-docx to parse DOCX resumes."],
            )

        document = Document(str(path))
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        return ParsedResume(text="\n".join(paragraphs).strip(), source_path=path, parser="python-docx", warnings=[])
