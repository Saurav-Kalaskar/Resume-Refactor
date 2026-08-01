import subprocess
import tempfile
import os
import re
from pathlib import Path
from typing import Optional, Tuple

# Use pdfLaTeX only - matches Overleaf engine
PDFLATEX_BIN = os.environ.get("PDFLATEX_BIN", "pdflatex")

# Progressive line-spacing steps used to squeeze content onto one page.
# Start at natural spacing (None = no override, preserves the author's layout),
# then tighten in small steps until it fits.
# ponytail: naive linespread squeeze with a hard floor. If content overflows even
# at the floor, the resume is genuinely too long — upgrade path is a font-size or
# geometry nudge, but that distorts the design, so we stop and report over-page
# instead of mangling the layout.
_LINESPREAD_STEPS = [None, 0.97, 0.94, 0.91, 0.88, 0.85]


def _inject_linespread(tex_content: str, spread: Optional[float]) -> str:
    if spread is None or "\\begin{document}" not in tex_content:
        return tex_content
    injection = f"\\linespread{{{spread}}}\n"
    return tex_content.replace("\\begin{document}", injection + "\\begin{document}", 1)


def _try_compile(tex_content: str) -> Tuple[Optional[bytes], Optional[str], Optional[int]]:
    """Compile LaTeX and return PDF bytes, error, and page count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(tex_content, encoding="utf-8")

        result = subprocess.run(
            [PDFLATEX_BIN, "-interaction=nonstopmode", "-output-directory", tmpdir, str(tex_path)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=120,
        )

        if result.returncode != 0:
            return None, f"pdflatex error: {result.stderr}", None

        pdf_path = Path(tmpdir) / "resume.pdf"
        if not pdf_path.exists():
            return None, "PDF not generated", None

        # Parse page count from stdout. pdflatex wraps the "Output written on
        # <path> (N page(s), ...)" line, so match across newlines (DOTALL).
        combined = result.stdout + result.stderr
        page_count = None
        match = re.search(r'Output written on .*?\((\d+)\s+pages?', combined, re.DOTALL)
        if match:
            page_count = int(match.group(1))
        else:
            # Fallback: page markers like [1] or [1{...}] — don't require a closing bracket.
            pages_found = re.findall(r'\[(\d+)[\]\s{]', combined)
            if pages_found:
                page_count = max(int(p) for p in pages_found)

        pdf_bytes = pdf_path.read_bytes()
        return pdf_bytes, None, page_count


def compile_tex(tex_content: str) -> Tuple[Optional[bytes], Optional[str]]:
    """Compile LaTeX to PDF, tightening line spacing progressively until it fits on one page.

    Returns (pdf_bytes, error). The PDF returned is the best (fewest-page) result found;
    if even the tightest spacing overflows, the last attempt is returned so the caller can
    still surface a preview.
    """
    best_pdf: Optional[bytes] = None
    best_pages: Optional[int] = None
    last_error: Optional[str] = None

    for spread in _LINESPREAD_STEPS:
        pdf_bytes, error, page_count = _try_compile(_inject_linespread(tex_content, spread))
        if error:
            last_error = error
            continue  # a compile error at one spread may still succeed at another

        # Track the best result seen so far (unknown page count is treated as worst).
        pages_rank = page_count if page_count is not None else 99
        if best_pages is None or pages_rank < best_pages:
            best_pdf, best_pages = pdf_bytes, pages_rank

        if page_count == 1:
            return pdf_bytes, None  # fits — stop tightening

    if best_pdf is not None:
        # Overflowed at every spread, but we have a compiled PDF — return it (no hard error).
        return best_pdf, None

    return None, last_error or "Failed to compile resume"
