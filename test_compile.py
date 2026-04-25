#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')
from app.compile import compile_tex

with open('resume.tex', 'r', encoding='utf-8') as f:
    tex = f.read()

pdf_bytes, error = compile_tex(tex)
if error:
    print("Error:", error)
else:
    print("PDF generated, size:", len(pdf_bytes))
    # Optionally write to file
    with open('resume_compiled.pdf', 'wb') as out:
        out.write(pdf_bytes)
    print("Wrote resume_compiled.pdf")
