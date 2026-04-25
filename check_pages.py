#!/usr/bin/env python3
import subprocess, tempfile, re, sys
from pathlib import Path

def test_compile(tex_content):
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(tex_content, encoding="utf-8")
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, str(tex_path)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=120,
        )
        # Extract page count from output
        combined = result.stdout + result.stderr
        # Look for the line with page count
        for line in combined.splitlines():
            if "Output written on" in line:
                print("Found line:", line)
                break
        match = re.search(r'\((\d+)\s+pages?', combined)
        pages = int(match.group(1)) if match else None
        if pages is None:
            # Debug: print last few lines
            print(f"DEBUG: Could not find page count. Last lines of stdout:")
            print('\n'.join(result.stdout.splitlines()[-10:]))
            print("Last lines of stderr:")
            print('\n'.join(result.stderr.splitlines()[-10:]))
        return pages, result.returncode, combined

if __name__ == "__main__":
    with open('resume.tex', 'r', encoding='utf-8') as f:
        tex = f.read()

    # Test original
    pages, rc, combined = test_compile(tex)
    print(f"Original: pages={pages}, rc={rc}")
    if pages and pages>1:
        print("Original already >1 page!")

    # Test with linespread 0.95
    tex_mod = tex.replace(r'\begin{document}', r'\linespread{0.95}' + '\n' + r'\begin{document}')
    pages, rc, combined = test_compile(tex_mod)
    print(f"Linespread 0.95: pages={pages}, rc={rc}")

    # Simulate bolding: add \textbf{} to some words
    # For testing, we'll bold all occurrences of "and" (case-sensitive)
    tex_bold = re.sub(r'\band\b', r'\\textbf{and}', tex_mod)
    pages, rc, combined = test_compile(tex_bold)
    print(f"With bolding: pages={pages}, rc={rc}")

    # Show snippet of log if needed
    if pages and pages>1:
        print("Log snippet:")
        print(combined[-2000:])
