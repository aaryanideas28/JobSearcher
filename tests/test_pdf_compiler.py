# File: tests/test_pdf_compiler.py
from __future__ import annotations

from src.utils.pdf_compiler import PDFCompiler


def test_inline_template_rendering() -> None:
    compiler = PDFCompiler()
    html = compiler.render_string("<h1>{{ name }}</h1>", {"name": "Ada"})
    assert "Ada" in html


def test_pdf_compiler_returns_bytes() -> None:
    compiler = PDFCompiler()
    pdf_bytes = compiler.compile_pdf("<html><body>Resume</body></html>")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
