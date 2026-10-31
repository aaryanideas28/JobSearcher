# File: src/utils/latex_compiler.py
"""LaTeX resume compiler: escape → render → compile → fit-to-one-page.

Supports Tectonic (preferred) and pdflatex as fallback engines.
If neither is found, raises LatexEngineNotFoundError with install instructions
so callers can gracefully fall back to DOCX.
"""

from __future__ import annotations

import base64
import copy
import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("storage_workspace")
TEMPLATE_DIR = WORKSPACE_ROOT / "templates" / "resume"
GENERATED_DIR = WORKSPACE_ROOT / "generated"

# ---------------------------------------------------------------------------
# Custom Jinja2 delimiters so they don't collide with LaTeX braces/backslashes
# ---------------------------------------------------------------------------
_JINJA_ENV: Environment | None = None


def _get_jinja_env() -> Environment:
    global _JINJA_ENV
    if _JINJA_ENV is None:
        _JINJA_ENV = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            block_start_string=r"\BLOCK{",
            block_end_string="}",
            variable_start_string=r"\VAR{",
            variable_end_string="}",
            comment_start_string=r"\COMMENT{",
            comment_end_string="}",
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )
        # Expose a |string filter alias
        _JINJA_ENV.filters["string"] = str
    return _JINJA_ENV


# ---------------------------------------------------------------------------
# LaTeX escaping
# ---------------------------------------------------------------------------

# Mapping of special LaTeX characters to their escaped equivalents
_LATEX_SPECIAL: list[tuple[str, str]] = [
    ("\\", r"\textbackslash{}"),  # must be first
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]

# Unicode replacements for common non-ASCII characters
_UNICODE_MAP: dict[str, str] = {
    "\u2018": "`",       # left single quote
    "\u2019": "'",       # right single quote / apostrophe
    "\u201c": "``",      # left double quote
    "\u201d": "''",      # right double quote
    "\u2013": "--",      # en dash
    "\u2014": "---",     # em dash
    "\u2022": r"\textbullet{}",   # bullet
    "\u2019": "'",
    "\u00e9": r"\'{e}",
    "\u00e8": r"\`{e}",
    "\u00ea": r"\^{e}",
    "\u00eb": r"\"{e}",
    "\u00e0": r"\`{a}",
    "\u00e2": r"\^{a}",
    "\u00e4": r"\"{a}",
    "\u00fc": r"\"{u}",
    "\u00f6": r"\"{o}",
    "\u00e7": r"\c{c}",
    "\u00f1": r"\~{n}",
    "\u00ed": r"\'{\i}",
    "\u2026": r"\ldots{}",
    "\u00a0": "~",       # non-breaking space
    "\u200b": "",        # zero-width space
}


def escape_latex(text: str) -> str:
    """Escape *text* so it is safe to embed in a LaTeX document.

    Handles:
    - All special LaTeX characters (& % $ # _ { } ~ ^ \\)
    - Unicode smart quotes, en/em dashes, bullets
    - Common accented characters via LaTeX commands
    - Any remaining non-ASCII characters via unicodedata decomposition or removal
    """
    if not text:
        return ""

    # 1. Unicode substitutions (before LaTeX escaping to avoid double-escaping)
    for char, replacement in _UNICODE_MAP.items():
        text = text.replace(char, replacement)

    # 2. LaTeX special characters (backslash first, then the rest)
    # We already replaced backslash with \textbackslash{} above in _UNICODE_MAP order;
    # handle it here explicitly in the correct order.
    result: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        replaced = False
        for special, esc in _LATEX_SPECIAL:
            if ch == special:
                result.append(esc)
                replaced = True
                break
        if not replaced:
            # 3. Handle remaining non-ASCII by decomposing or dropping
            if ord(ch) > 127:
                # Try NFKD decomposition → keep ASCII base
                decomposed = unicodedata.normalize("NFKD", ch)
                ascii_part = decomposed.encode("ascii", errors="ignore").decode("ascii")
                result.append(ascii_part if ascii_part else "")
            else:
                result.append(ch)
        i += 1

    return "".join(result)


def _escape_dict(obj: Any) -> Any:
    """Recursively escape all string values in a nested dict/list structure."""
    if isinstance(obj, str):
        return escape_latex(obj)
    if isinstance(obj, list):
        return [_escape_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _escape_dict(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def render_tex(resume_json: dict[str, Any], template_name: str = "jake_resume.tex.j2") -> str:
    """Render *resume_json* into a LaTeX string using the named Jinja2 template.

    All string values in *resume_json* are LaTeX-escaped automatically.
    The template receives the escaped data plus rendering hints
    (font_size, margin_*).
    """
    env = _get_jinja_env()
    template = env.get_template(template_name)

    escaped = _escape_dict(copy.deepcopy(resume_json))

    # Ensure required top-level keys exist with sensible defaults
    escaped.setdefault("contact", {})
    escaped["contact"].setdefault("name", "")
    escaped.setdefault("education", [])
    escaped.setdefault("experience", [])
    escaped.setdefault("projects", [])
    escaped.setdefault("technical_skills", {})
    escaped.setdefault("achievements", [])

    # Rendering hints (caller may override via resume_json["_render"])
    render_hints = resume_json.get("_render", {})
    escaped["font_size"] = render_hints.get("font_size", "11pt")
    escaped["margin_top"] = render_hints.get("margin_top", "0.5in")
    escaped["margin_bottom"] = render_hints.get("margin_bottom", "0.5in")
    escaped["margin_left"] = render_hints.get("margin_left", "0.5in")
    escaped["margin_right"] = render_hints.get("margin_right", "0.5in")

    return template.render(**escaped)


# ---------------------------------------------------------------------------
# LaTeX engine detection
# ---------------------------------------------------------------------------

class LatexEngineNotFoundError(RuntimeError):
    """Raised when neither tectonic nor pdflatex is available."""


def _find_latex_engine() -> tuple[str, str]:
    """Return (engine_name, executable_path) for the best available engine.

    Prefers tectonic, falls back to pdflatex.
    Raises LatexEngineNotFoundError with install instructions if neither found.
    """
    for name in ("tectonic", "pdflatex"):
        path = shutil.which(name)
        if path:
            return name, path

    raise LatexEngineNotFoundError(
        "No LaTeX engine found on PATH. Resume will fall back to DOCX format.\n"
        "To enable PDF/LaTeX output, install one of the following:\n"
        "  • Tectonic (recommended, self-contained):\n"
        "      Windows: winget install tectonic  OR  scoop install tectonic\n"
        "      macOS:   brew install tectonic\n"
        "      Linux:   cargo install tectonic  OR see https://tectonic-typesetting.github.io\n"
        "  • MiKTeX: https://miktex.org/download\n"
        "  • TeX Live: https://tug.org/texlive/\n"
        "  • Overleaf (cloud, no install): use /api/resume/{id}/overleaf"
    )


# ---------------------------------------------------------------------------
# PDF compilation
# ---------------------------------------------------------------------------

def compile_pdf(tex_str: str, out_dir: str | Path, stem: str = "resume") -> Path:
    """Compile *tex_str* to PDF and save in *out_dir*.

    Uses ``tectonic`` if available, otherwise ``pdflatex`` (run twice).
    All compilation is done in a temporary directory; on success the PDF is
    moved to *out_dir*.  On failure the last 40 lines of the engine log are
    embedded in a ``LatexCompilationError``.

    Args:
        tex_str: Complete LaTeX source string.
        out_dir: Directory where the output PDF should be placed.
        stem:    Base filename (without extension) for the output PDF.

    Returns:
        Path to the compiled PDF.

    Raises:
        LatexEngineNotFoundError: If neither tectonic nor pdflatex is on PATH.
        LatexCompilationError: If the engine reports an error.
    """
    engine_name, engine_path = _find_latex_engine()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="latex_") as tmp:
        tmp_path = Path(tmp)
        tex_file = tmp_path / f"{stem}.tex"
        tex_file.write_text(tex_str, encoding="utf-8")

        if engine_name == "tectonic":
            cmd = [
                engine_path,
                "-no-shell-escape",
                "--outdir", str(tmp_path),
                str(tex_file),
            ]
            runs = 1
        else:
            # pdflatex needs two passes for cross-references
            cmd = [
                engine_path,
                "-interaction=nonstopmode",
                "-no-shell-escape",
                f"-output-directory={tmp_path}",
                str(tex_file),
            ]
            runs = 2

        log_file = tmp_path / f"{stem}.log"
        last_result: subprocess.CompletedProcess | None = None

        for _ in range(runs):
            try:
                last_result = subprocess.run(
                    cmd,
                    cwd=tmp_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired as exc:
                raise LatexCompilationError(
                    f"LaTeX engine timed out after 60s.\n{exc}"
                ) from exc

        pdf_tmp = tmp_path / f"{stem}.pdf"
        if not pdf_tmp.exists() or (last_result and last_result.returncode != 0):
            # Extract last 40 lines of log
            log_tail = ""
            if log_file.exists():
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                log_tail = "\n".join(lines[-40:])
            elif last_result:
                log_tail = (last_result.stdout or "") + (last_result.stderr or "")
            raise LatexCompilationError(
                f"LaTeX compilation failed ({engine_name}).\n"
                f"Last 40 lines of log:\n{log_tail}"
            )

        dest = out_dir / f"{stem}.pdf"
        shutil.copy2(pdf_tmp, dest)
        logger.info("Compiled PDF: %s (engine=%s)", dest, engine_name)
        return dest


class LatexCompilationError(RuntimeError):
    """Raised when the LaTeX engine fails to produce a PDF."""


# ---------------------------------------------------------------------------
# Page count
# ---------------------------------------------------------------------------

def page_count(pdf_path: str | Path) -> int:
    """Return the number of pages in *pdf_path* using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception as exc:
        logger.warning("Could not count pages in %s: %s", pdf_path, exc)
        return 1


# ---------------------------------------------------------------------------
# fit_to_one_page
# ---------------------------------------------------------------------------

_FONT_SIZES = ["11pt", "10.5pt", "10pt"]
_MARGIN_STEPS = [
    {"margin_top": "0.5in", "margin_bottom": "0.5in", "margin_left": "0.5in", "margin_right": "0.5in"},
    {"margin_top": "0.4in", "margin_bottom": "0.4in", "margin_left": "0.45in", "margin_right": "0.45in"},
    {"margin_top": "0.35in", "margin_bottom": "0.35in", "margin_left": "0.4in", "margin_right": "0.4in"},
]
_MAX_BULLETS = [4, 3, 2]


def fit_to_one_page(
    resume_json: dict[str, Any],
    out_dir: str | Path = GENERATED_DIR,
    stem: str = "resume_fitted",
    template_name: str = "jake_resume.tex.j2",
) -> Path:
    """Compile and progressively trim *resume_json* until output is ≤ 1 page.

    Strategy (up to 4 iterations):
      1. Reduce font size 11pt → 10.5pt → 10pt.
      2. Tighten margins slightly.
      3. Cap bullets per role (4 → 3 → 2).
      4. Drop the oldest experience entry.
      Never invents new content.

    Returns the path of the final (one-page) PDF.
    Raises LatexEngineNotFoundError if no engine is installed (caller should
    fall back to DOCX).
    """
    data = copy.deepcopy(resume_json)
    out_dir = Path(out_dir)

    for iteration in range(4):
        font_idx = min(iteration, len(_FONT_SIZES) - 1)
        margin_idx = min(iteration, len(_MARGIN_STEPS) - 1)
        bullet_cap = _MAX_BULLETS[min(iteration, len(_MAX_BULLETS) - 1)]

        render_hints = {
            "font_size": _FONT_SIZES[font_idx],
            **_MARGIN_STEPS[margin_idx],
        }
        data["_render"] = render_hints

        # Cap bullets
        _cap_bullets(data, bullet_cap)

        tex_str = render_tex(data, template_name)

        try:
            pdf_path = compile_pdf(tex_str, out_dir, stem=f"{stem}_iter{iteration}")
        except LatexEngineNotFoundError:
            raise
        except LatexCompilationError as exc:
            logger.error("Fit-to-one-page compile error on iter %d: %s", iteration, exc)
            raise

        pages = page_count(pdf_path)
        logger.info("fit_to_one_page iter=%d pages=%d font=%s", iteration, pages, _FONT_SIZES[font_idx])

        if pages <= 1:
            return pdf_path

        # Drop the oldest (last) experience entry for next iteration
        if data.get("experience") and len(data["experience"]) > 1:
            data["experience"] = data["experience"][:-1]

    # Final attempt with the most aggressive settings
    tex_str = render_tex(data, template_name)
    pdf_path = compile_pdf(tex_str, out_dir, stem=f"{stem}_final")
    return pdf_path


def _cap_bullets(data: dict[str, Any], cap: int) -> None:
    """Trim bullet lists in experience and projects to at most *cap* items."""
    for section_key in ("experience", "projects"):
        for entry in data.get(section_key, []):
            bullets = entry.get("bullets", [])
            if len(bullets) > cap:
                entry["bullets"] = bullets[:cap]


# ---------------------------------------------------------------------------
# Overleaf "Open in Overleaf" helper
# ---------------------------------------------------------------------------

def build_overleaf_url(tex_str: str, filename: str = "resume.tex") -> str:
    """Return an 'Open in Overleaf' URL using the documented data-URI method.

    Per Overleaf's documented open-in-Overleaf v2 API:
    POST https://www.overleaf.com/docs  with  snip_uri (data URI)

    Since we return a URL that the browser can POST via a form, we embed the
    .tex source as a base64 data URI.  The caller is responsible for rendering
    the redirect form in the browser.

    Returns the base64-encoded tex content; the endpoint builds the form POST.
    """
    encoded = base64.b64encode(tex_str.encode("utf-8")).decode("ascii")
    data_uri = f"data:application/x-tex;base64,{encoded}"
    # The actual POST is done client-side; we return the data URI.
    return data_uri


# ---------------------------------------------------------------------------
# High-level convenience: render + compile
# ---------------------------------------------------------------------------

def build_latex_resume(
    resume_json: dict[str, Any],
    out_dir: str | Path = GENERATED_DIR,
    stem: str = "resume",
    template_name: str = "jake_resume.tex.j2",
    fit_one_page: bool = True,
) -> dict[str, Any]:
    """Full pipeline: render → compile → (optionally fit to one page).

    Returns a dict with keys:
      tex_str   – rendered LaTeX source
      pdf_path  – Path to compiled PDF (or None if engine not found)
      pages     – page count (int)
      overleaf_data_uri – base64 data URI for Overleaf POST
      engine_found – bool
      fallback_reason – str | None
    """
    tex_str = render_tex(resume_json, template_name)
    overleaf_uri = build_overleaf_url(tex_str)
    out_dir = Path(out_dir)

    try:
        if fit_one_page:
            pdf_path = fit_to_one_page(resume_json, out_dir=out_dir, stem=stem, template_name=template_name)
        else:
            pdf_path = compile_pdf(tex_str, out_dir=out_dir, stem=stem)
        pages = page_count(pdf_path)
        return {
            "tex_str": tex_str,
            "pdf_path": pdf_path,
            "pages": pages,
            "overleaf_data_uri": overleaf_uri,
            "engine_found": True,
            "fallback_reason": None,
        }
    except LatexEngineNotFoundError as exc:
        logger.warning("LaTeX engine not found — falling back to DOCX. %s", exc)
        return {
            "tex_str": tex_str,
            "pdf_path": None,
            "pages": None,
            "overleaf_data_uri": overleaf_uri,
            "engine_found": False,
            "fallback_reason": str(exc),
        }

