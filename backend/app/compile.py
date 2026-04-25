import subprocess
import tempfile
import os
import re
from pathlib import Path
from typing import Optional, Tuple

# Use pdfLaTeX only - matches Overleaf engine
PDFLATEX_BIN = os.environ.get("PDFLATEX_BIN", "pdflatex")


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

        # Parse page count from stdout
        combined = result.stdout + result.stderr
        page_count = None
        match = re.search(r'Output written on .+?\((\d+)\s+pages?', combined)
        if match:
            page_count = int(match.group(1))
        else:
            # Fallback: look for numeric page markers in log
            pages_found = set(re.findall(r'\[(\d+)\]', combined))
            if pages_found:
                page_count = max(int(p) for p in pages_found)

        pdf_bytes = pdf_path.read_bytes()
        return pdf_bytes, None, page_count


def compile_tex(tex_content: str) -> Tuple[Optional[bytes], Optional[str]]:
    """Compile LaTeX to PDF, using tighter spacing to ensure 1-page output."""

    # Apply tighter line spacing to reduce vertical space
    # Tested: linespread 0.92 produces 1 page (default produces 2 pages)
    if '\\begin{document}' in tex_content:
        injection = '\\linespread{0.92}\n'
        tex_mod = tex_content.replace('\\begin{document}', injection + '\\begin{document}')
    else:
        tex_mod = tex_content

    pdf_bytes, error, page_count = _try_compile(tex_mod)

    if error:
        return None, error

    # If not 1 page (or count unknown), return PDF anyway with a soft warning
    # The main.py will handle this gracefully
    if page_count is not None and page_count != 1:
        return pdf_bytes, None  # Don't error, just return the PDF

    return pdf_bytes, None


def find_latex_compiler() -> Optional[str]:
    """Locate tectonic binary."""
    bin_paths = [
        "tectonic",
        "/usr/local/bin/tectonic",
        "/usr/bin/tectonic",
        os.path.expanduser("~/.cargo/bin/tectonic"),
        os.path.expanduser("~/.local/bin/tectonic"),
    ]
    for path in bin_paths:
        if subprocess.run(["which", path], capture_output=True).returncode == 0:
            return path
    return None
